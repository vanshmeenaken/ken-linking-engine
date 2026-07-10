"""Layer 4 of Shrey's 4-layer adjacency method — LLM final judge.

Layers 2+3 (analysis/subject_similarity.py) get precision from ~0% to
genuinely high using deterministic weighting + a compound-topic gate alone
(validated live: country_region 551 -> 9 candidates, all on-subject). This
layer exists for the residual cases a word-overlap metric can't resolve —
two titles about the exact same subject with almost no shared vocabulary
("EV Charging Infrastructure" vs "Plug-In Vehicle Power Points"), or two
titles with real overlap but different subjects TF-IDF can't tell apart.
On the earlier kr-interlink project, embeddings + a cross-encoder reranker
were tried here and failed (ranked "automotive parts" #1 for a coolant
query, robotics above healthcare for an AI query) — only an LLM with actual
domain knowledge enforced "directly about the exact subject."

Optional and credential-gated: if ANTHROPIC_API_KEY isn't set, judge()
returns None (not True/False) so callers fall back to the Layers 2+3
verdict rather than blocking or crashing. Never required for the pipeline
to run.
"""

from __future__ import annotations

import json
import os

_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM_PROMPT = """You are a market-research subject-matching judge. You will \
be shown two report titles that already passed a coarse similarity filter \
(same broad industry, some vocabulary overlap). Your only job: decide if \
they are about the SAME core subject at different geographies/angles \
(genuinely "adjacent" reports a reader of one would want linked to the \
other), or if they only share generic words/industry and are actually \
about different subjects.

Rules:
- Full subject must match, not half. "Automotive Coolant" and "Automotive \
Parts" share "automotive" but are different subjects -> NOT a match.
- Same broad industry alone is never enough.
- A compound topic ("AI in Medicine") only matches another instance of the \
SAME compound ("AI in Healthcare"), not just one half ("Herbal Medicine" or \
"AI in Robotics").
- When genuinely unsure, answer false — never pad a "maybe" into a match.

Respond with ONLY a JSON object: {"match": true or false, "reason": "one \
short sentence"}. No markdown, no other text."""


def is_available() -> bool:
    """True if a real LLM judgment can be made (API key configured)."""
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def judge(title_a: str, title_b: str) -> bool | None:
    """Ask Claude whether two titles are genuinely about the same subject.

    Returns True/False, or None if no API key is configured (graceful
    skip — callers should treat None as "no Layer 4 opinion, trust
    Layers 2+3") or if the call fails for any reason (never let an LLM
    outage break the deterministic pipeline)."""
    if not is_available():
        return None
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        response = client.messages.create(
            model=_MODEL,
            max_tokens=200,
            system=_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f'Title A: "{title_a}"\nTitle B: "{title_b}"',
            }],
        )
        raw = response.content[0].text.strip()
        clean = raw.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(clean)
        return bool(parsed["match"])
    except Exception:
        return None
