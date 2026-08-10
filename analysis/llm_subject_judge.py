"""Optional final market-and-technology relevance judge.

The deterministic gate runs first. This module handles residual semantic cases
that lexical overlap cannot resolve, such as synonyms or related technologies.
External calls are opt-in through Agent 3's ``--use-llm-judge`` flag; normal
runs do not disclose report titles to a third party.
"""

from __future__ import annotations

import json
import os

_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM_PROMPT = """You judge whether two market-research reports should be interlinked.
Market relevance is primary and technology relevance is secondary. Geography
must never create relevance; it only classifies a relationship after the pair
passes.

Accept when BOTH are true:
1. The markets are the same, synonymous, parent/child, or genuinely close in
   the same business ecosystem.
2. Their products, operating technology, application, or service model are
   the same or closely connected.

Valid examples:
- Global Rehabilitation Equipment -> UAE Rehabilitation Products (same market,
  regional geography).
- Global Rehabilitation Equipment -> Global Rehabilitation Robots (adjacent
  technology within the rehabilitation market).
- Global Rehabilitation Equipment -> Qatar Rehabilitation Centers (adjacent
  downstream service and user of the equipment).
- Food Preservatives -> Food Additives or Food Stabilizers (closely related
  formulation markets).

Reject when the pair only shares an industry, geography, broad customer, or
ambiguous keyword. Examples to reject:
- Machine Tools -> Power Tools.
- Radiology Information Systems -> Hospital Information Systems.
- Blood Screening -> Blood IV Warmers.
- AI in Medicine -> Herbal Medicine.

When unsure, reject. Respond with ONLY JSON:
{"match": true or false, "reason": "one short sentence"}.
"""


def is_available() -> bool:
    """True if a real LLM judgment can be made (API key configured)."""
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def judge(title_a: str, title_b: str, allow_nvidia: bool = False) -> bool | None:
    """Ask Claude whether two titles are genuinely about the same subject.

    Returns True/False, or None if no API key is configured (graceful
    skip — callers should treat None as "no Layer 4 opinion, trust
    Layers 2+3") or if the call fails for any reason (never let an LLM
    outage break the deterministic pipeline)."""
    try:
        if is_available():
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
        elif allow_nvidia and os.getenv("NVIDIA_API_KEY"):
            from openai import OpenAI

            client = OpenAI(
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=os.environ["NVIDIA_API_KEY"],
            )
            response = client.chat.completions.create(
                model="meta/llama-3.1-8b-instruct",
                temperature=0.0,
                max_tokens=120,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content":
                     f'Title A: "{title_a}"\nTitle B: "{title_b}"'},
                ],
            )
            raw = response.choices[0].message.content.strip()
        else:
            return None
        clean = raw.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(clean)
        return bool(parsed["match"])
    except Exception:
        return None
