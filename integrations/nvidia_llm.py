"""NVIDIA NIM client for natural-language sentence rewriting.

Used only for one narrow, low-risk task: rewriting an EXISTING sentence to
carry an anchor link naturally, given the sentence and anchor already
determined by the deterministic pipeline (analysis/contextual_placement.py,
analysis/sentence_composer.py). The LLM never chooses WHERE a link goes,
WHICH target to link to, or WHAT anchor text to use - all of that stays
deterministic (project discipline: deterministic before LLM). It only
rephrases prose, and its output is verified before use.

Fails closed: any error (missing key, network, malformed response) returns
None so the caller falls back to the deterministic template rewrite in
analysis/sentence_composer.py. The pipeline must never break because an
external API is unavailable.
"""
from __future__ import annotations

import os
import re

BASE_URL = "https://integrate.api.nvidia.com/v1"

# Tried in order. A single NVIDIA-hosted model can be queue-congested while
# the rest of the endpoint is perfectly healthy: llama-3.3-70b timed out on
# every request for an hour (45s+ each, no response) while llama-3.1-70b
# answered the identical prompt in 1.6s and GET /models returned in 0.3s.
# Diagnosing that as "the API is down" was wrong, so the model is no longer a
# single point of failure - the first model that responds wins.
MODELS = (
    "meta/llama-3.1-70b-instruct",          # strongest that responds reliably
    "meta/llama-3.3-70b-instruct",          # preferred when not congested
    "nvidia/llama-3.3-nemotron-super-49b-v1",
    "meta/llama-3.1-8b-instruct",           # fast last resort
)
MODEL = MODELS[0]  # kept for callers/tests that reference a single model

_SYSTEM_PROMPT = (
    "You rewrite ONE sentence from a market research report so it naturally "
    "mentions a related report, for an internal link. Rules, all mandatory:\n"
    "1. Keep every existing fact, number, percentage, and claim in the "
    "original sentence EXACTLY as written - do not change, round, or drop "
    "any of them.\n"
    "2. Do not invent any NEW fact, number, or claim about either market.\n"
    "3. Weave in the exact anchor phrase you are given, verbatim, as a "
    "natural reference to that other report - do not paraphrase or "
    "shorten the anchor text.\n"
    "4. Keep it to ONE sentence, professional, analytical tone (market "
    "research register, not casual).\n"
    "5. Output ONLY the rewritten sentence. No preamble, no quotes, no "
    "explanation, no markdown."
)


def api_keys() -> list[str]:
    """Every configured NVIDIA key, in order: NVIDIA_API_KEY, then
    NVIDIA_API_KEY_2, _3, ... Multiple keys exist so generation can run
    several requests in parallel (one key per worker) - the API is slow
    per call (~10s), so concurrency is what makes a full run practical.
    """
    keys = []
    primary = os.environ.get("NVIDIA_API_KEY")
    if primary:
        keys.append(primary)
    i = 2
    while (extra := os.environ.get(f"NVIDIA_API_KEY_{i}")):
        keys.append(extra)
        i += 1
    return keys


# A request must fail FAST, not hang. The OpenAI client defaults to a 600s
# timeout with retries, so when the NVIDIA endpoint stalls (free-tier quota
# exhaustion looks exactly like a stall) a single call can block for ten
# minutes and a bulk run appears frozen with no output - which is exactly
# what happened before this was set. One attempt, bounded wait, then the
# caller's deterministic fallback takes over.
# Kept short because MODELS is tried in order: a long timeout multiplied by
# the model list is what makes a congested endpoint feel like a hang. A
# healthy model answers this prompt in 1-2s, so 20s is generous.
REQUEST_TIMEOUT_SECONDS = 20.0


def _client(api_key: str | None = None):
    api_key = api_key or os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        return None
    from openai import OpenAI
    return OpenAI(base_url=BASE_URL, api_key=api_key,
                  timeout=REQUEST_TIMEOUT_SECONDS, max_retries=0)


def normalise_punctuation(text: str) -> str:
    """Match the punctuation style of the scraped page text: no em/en dashes
    or smart quotes. analysis/contextual_placement._clean() does the same for
    crawled prose, so a rewritten sentence sits beside the original without a
    visible style shift, and the web team can paste it as-is."""
    repl = {"—": " - ", "–": "-", "’": "'", "‘": "'",
            "“": '"', "”": '"', "…": "..."}
    for a, b in repl.items():
        text = text.replace(a, b)
    return re.sub(r"\s{2,}", " ", text).strip()


def _restore_exact_anchor(rewritten: str, anchor: str) -> str:
    """Repair the one anchor deviation worth repairing: an anchor containing
    "&" comes back with "and" (or the reverse), because that is how the model
    naturally writes prose. The anchor becomes the clickable link text, so it
    must match the anchor bank character for character - but rejecting the
    whole rewrite over "&" vs "and" would waste a good sentence. Any other
    deviation is still rejected by the caller.
    """
    if not rewritten or not anchor or anchor in rewritten:
        return rewritten
    for a, b in (("&", "and"), ("and", "&")):
        if a in anchor:
            variant = anchor.replace(a, b)
            if variant in rewritten:
                return rewritten.replace(variant, anchor)
    return rewritten


# Digits with optional thousand separators, an optional decimal part, and an
# optional percent sign. Deliberately does NOT swallow trailing punctuation:
# an earlier version used \d[\d,.]*%? which captured "2031." (including the
# full stop) from the end of a sentence, then failed to find it in a rewrite
# that ended "...2031," - rejecting good rewrites over punctuation alone.
# A comma is only part of a number when digits follow it, so "2025," at the
# end of a clause yields "2025" and not "2025,". The looser \d[\d,]* let the
# trailing comma in, which then failed to match a rewrite that punctuated the
# same figure differently - the same class of false negative as the trailing
# full stop.
_NUMBER_RE = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?%?")


def _contains_all_numbers(original: str, rewritten: str) -> bool:
    """Every number in the original must still appear in the rewrite -
    the hard check that the model did not drop or alter a fact."""
    return all(n in rewritten for n in _NUMBER_RE.findall(original))


def llm_weave_sentence(sentence: str, anchor: str,
                       api_key: str | None = None) -> str | None:
    """Rewrite `sentence` to naturally carry `anchor`. Returns None on any
    failure (missing key, API error, or a response that fails verification)
    so the caller falls back to the deterministic template. `api_key` lets a
    parallel worker use its own key from api_keys()."""
    client = _client(api_key)
    if client is None or not sentence.strip() or not anchor.strip():
        return None
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"Original sentence: {sentence}\n"
            f"Anchor phrase to weave in (verbatim): {anchor}")},
    ]
    for model in MODELS:
        try:
            resp = client.chat.completions.create(
                model=model, messages=messages, max_tokens=200,
                temperature=0.4)
            rewritten = normalise_punctuation(
                (resp.choices[0].message.content or "").strip().strip('"'))
        except Exception:
            continue  # congested or unavailable model: try the next one
        rewritten = _restore_exact_anchor(rewritten, anchor)
        if not rewritten or anchor not in rewritten:
            return None  # model answered but broke the rules - do not retry
        if not _contains_all_numbers(sentence, rewritten):
            return None
        return rewritten
    return None  # every model failed; caller falls back to the template
