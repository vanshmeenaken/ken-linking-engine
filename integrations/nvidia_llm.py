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

MODEL = "meta/llama-3.3-70b-instruct"
BASE_URL = "https://integrate.api.nvidia.com/v1"

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
REQUEST_TIMEOUT_SECONDS = 45.0


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


def _contains_all_numbers(original: str, rewritten: str) -> bool:
    """Every number in the original must still appear in the rewrite -
    the hard check that the model did not drop or alter a fact."""
    original_nums = re.findall(r"\d[\d,.]*%?", original)
    return all(n in rewritten for n in original_nums)


def llm_weave_sentence(sentence: str, anchor: str,
                       api_key: str | None = None) -> str | None:
    """Rewrite `sentence` to naturally carry `anchor`. Returns None on any
    failure (missing key, API error, or a response that fails verification)
    so the caller falls back to the deterministic template. `api_key` lets a
    parallel worker use its own key from api_keys()."""
    client = _client(api_key)
    if client is None or not sentence.strip() or not anchor.strip():
        return None
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": (
                    f"Original sentence: {sentence}\n"
                    f"Anchor phrase to weave in (verbatim): {anchor}")},
            ],
            max_tokens=200,
            temperature=0.4,
        )
        rewritten = normalise_punctuation(
            (resp.choices[0].message.content or "").strip().strip('"'))
    except Exception:
        return None
    if not rewritten or anchor not in rewritten:
        return None
    if not _contains_all_numbers(sentence, rewritten):
        return None
    return rewritten
