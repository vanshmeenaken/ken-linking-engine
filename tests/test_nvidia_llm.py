"""Tests for integrations/nvidia_llm.py: the LLM-based sentence rewrite and
its fact-preservation verification. No real network calls - the OpenAI
client is monkeypatched throughout."""

import integrations.nvidia_llm as nvidia_llm
from integrations.nvidia_llm import _contains_all_numbers, llm_weave_sentence


# ── number-preservation check ────────────────────────────────────────────────

def test_contains_all_numbers_true_when_preserved():
    original = "The market grew at a CAGR of 6.8% to reach USD 130 million."
    rewritten = "The market grew at a CAGR of 6.8% to reach USD 130 million, a trend also shaping the X Market."
    assert _contains_all_numbers(original, rewritten)


def test_contains_all_numbers_false_when_dropped():
    original = "The market grew at a CAGR of 6.8% to reach USD 130 million."
    rewritten = "The market grew steadily, a trend also shaping the X Market."
    assert not _contains_all_numbers(original, rewritten)


def test_contains_all_numbers_false_when_altered():
    original = "The market is worth USD 130 million."
    rewritten = "The market is worth USD 150 million, similar to the X Market."
    assert not _contains_all_numbers(original, rewritten)


# ── fails closed: missing key, network error, bad response ──────────────────

def test_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    assert llm_weave_sentence("A sentence.", "X Market") is None


def test_returns_none_on_empty_inputs(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "fake-key-for-test")
    assert llm_weave_sentence("", "X Market") is None
    assert llm_weave_sentence("A sentence.", "") is None


class _FakeChoice:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})()


class _FakeCompletions:
    def __init__(self, content):
        self._content = content

    def create(self, **kwargs):
        return type("R", (), {"choices": [_FakeChoice(self._content)]})()


class _FakeChat:
    def __init__(self, content):
        self.completions = _FakeCompletions(content)


class _FakeClient:
    def __init__(self, content):
        self.chat = _FakeChat(content)


def _mock_client(monkeypatch, content):
    monkeypatch.setenv("NVIDIA_API_KEY", "fake-key-for-test")
    monkeypatch.setattr(nvidia_llm, "_client",
                        lambda api_key=None: _FakeClient(content))


def test_accepts_a_valid_rewrite(monkeypatch):
    _mock_client(monkeypatch, (
        'The market grew at 6.8% CAGR, a pattern also visible in the '
        'X Market.'))
    result = llm_weave_sentence("The market grew at 6.8% CAGR.", "X Market")
    assert result is not None
    assert "X Market" in result
    assert "6.8%" in result


def test_rejects_response_missing_the_anchor(monkeypatch):
    _mock_client(monkeypatch, "The market grew at 6.8% CAGR, a broader trend.")
    result = llm_weave_sentence("The market grew at 6.8% CAGR.", "X Market")
    assert result is None


def test_rejects_response_that_drops_a_number(monkeypatch):
    _mock_client(monkeypatch, "The market grew steadily, similar to the X Market.")
    result = llm_weave_sentence("The market grew at 6.8% CAGR.", "X Market")
    assert result is None


def test_strips_wrapping_quotes(monkeypatch):
    _mock_client(monkeypatch, '"The market grew at 6.8% CAGR, per the X Market."')
    result = llm_weave_sentence("The market grew at 6.8% CAGR.", "X Market")
    assert result is not None
    assert not result.startswith('"')


def test_api_exception_returns_none(monkeypatch):
    class _BrokenCompletions:
        def create(self, **kwargs):
            raise RuntimeError("network down")

    class _BrokenChat:
        completions = _BrokenCompletions()

    class _BrokenClient:
        chat = _BrokenChat()

    monkeypatch.setenv("NVIDIA_API_KEY", "fake-key-for-test")
    monkeypatch.setattr(nvidia_llm, "_client",
                        lambda api_key=None: _BrokenClient())
    assert llm_weave_sentence("A sentence.", "X Market") is None


# ── punctuation normalisation (match the scraped-page style) ─────────────────

from integrations.nvidia_llm import normalise_punctuation


def test_normalise_punctuation_removes_long_dashes_and_smart_quotes():
    raw = "The market grew \u2014 driven by demand \u2013 across the \u201cregion\u201d\u2019s hubs\u2026"
    out = normalise_punctuation(raw)
    for ch in ("\u2014", "\u2013", "\u201c", "\u201d", "\u2019", "\u2026"):
        assert ch not in out


def test_normalise_punctuation_collapses_double_spaces():
    assert "  " not in normalise_punctuation("The  market   grew strongly.")


def test_normalise_punctuation_preserves_numbers():
    raw = "Worth USD 1.2 billion in 2025 \u2014 growing at 12.75% CAGR."
    out = normalise_punctuation(raw)
    for n in ("1.2", "2025", "12.75%"):
        assert n in out


def test_llm_output_is_punctuation_normalised(monkeypatch):
    _mock_client(monkeypatch,
                 "The market grew at 6.8% CAGR \u2014 mirroring the X Market.")
    result = llm_weave_sentence("The market grew at 6.8% CAGR.", "X Market")
    assert result is not None
    assert "\u2014" not in result
    assert "X Market" in result
