"""Tests for Layer 4 — LLM final judge (analysis/llm_subject_judge.py).
Credential-gated and optional: must never raise, never block the
deterministic pipeline (Layers 1-3) when unavailable or when the API errors."""

import types

import pytest

from analysis import llm_subject_judge as mod


def test_unavailable_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert mod.is_available() is False


def test_available_with_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    assert mod.is_available() is True


def test_judge_returns_none_gracefully_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert mod.judge("India EV Market", "Vietnam EV Market") is None


def _fake_anthropic_module(response_text):
    """Build a fake `anthropic` module whose client returns response_text."""
    class FakeContent:
        def __init__(self, text):
            self.text = text

    class FakeResponse:
        def __init__(self, text):
            self.content = [FakeContent(text)]

    class FakeMessages:
        def create(self, **kwargs):
            return FakeResponse(response_text)

    class FakeClient:
        def __init__(self, api_key):
            self.messages = FakeMessages()

    fake_mod = types.ModuleType("anthropic")
    fake_mod.Anthropic = FakeClient
    return fake_mod


def test_judge_true_on_match(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    monkeypatch.setitem(
        __import__("sys").modules, "anthropic",
        _fake_anthropic_module('{"match": true, "reason": "same subject"}'),
    )
    assert mod.judge("India EV Market", "Vietnam EV Market") is True


def test_judge_false_on_no_match(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    monkeypatch.setitem(
        __import__("sys").modules, "anthropic",
        _fake_anthropic_module('{"match": false, "reason": "different subject"}'),
    )
    assert mod.judge("Automotive Coolant Market", "Automotive Parts Market") is False


def test_judge_strips_markdown_fences(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    monkeypatch.setitem(
        __import__("sys").modules, "anthropic",
        _fake_anthropic_module('```json\n{"match": true, "reason": "ok"}\n```'),
    )
    assert mod.judge("A", "B") is True


def test_judge_returns_none_on_malformed_response(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    monkeypatch.setitem(
        __import__("sys").modules, "anthropic",
        _fake_anthropic_module("not json at all"),
    )
    assert mod.judge("A", "B") is None


def test_judge_returns_none_when_client_raises(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")

    class RaisingClient:
        def __init__(self, api_key):
            raise RuntimeError("network down")

    fake_mod = types.ModuleType("anthropic")
    fake_mod.Anthropic = RaisingClient
    monkeypatch.setitem(__import__("sys").modules, "anthropic", fake_mod)
    assert mod.judge("A", "B") is None
