"""Unit tests for the AI narrative layer, focused on the deterministic fallback
and the provider-failover behaviour (never the real network call)."""

from __future__ import annotations

import json

import httpx
import pytest

from app.services.ai import (
    GroqProvider,
    InsightService,
    Narrative,
    OllamaProvider,
    TemplateProvider,
    _build_default_primary,
    _parse_narrative_json,
)

pytestmark = pytest.mark.unit


class FailingProvider:
    name = "broken"

    def generate(self, context: dict) -> Narrative:
        raise RuntimeError("simulated provider outage")


class StubProvider:
    name = "stub"

    def __init__(self, narrative: Narrative) -> None:
        self._narrative = narrative

    def generate(self, context: dict) -> Narrative:
        return self._narrative


class TestTemplateProviderPortfolio:
    def test_generates_headline_and_summary(self) -> None:
        provider = TemplateProvider()
        context = {
            "scope": "portfolio",
            "product_count": 10,
            "forecast_total_units": 1000,
            "history_total_units": 900,
            "growth_pct": 12.5,
            "open_exception_count": 3,
            "critical_exception_count": 1,
            "top_growing": ["A", "B"],
            "top_declining": ["C"],
        }
        narrative = provider.generate(context)
        assert "10" in narrative.headline
        assert narrative.generated_by == "template"
        assert len(narrative.recommendations) >= 2
        assert any("critical" in rec.lower() for rec in narrative.recommendations)

    def test_no_open_exceptions_says_so(self) -> None:
        provider = TemplateProvider()
        context = {"scope": "portfolio", "product_count": 5, "open_exception_count": 0}
        narrative = provider.generate(context)
        assert "No planning exceptions" in narrative.summary


class TestTemplateProviderProduct:
    def test_growing_product_gets_growth_recommendation(self) -> None:
        provider = TemplateProvider()
        context = {
            "scope": "product",
            "product_name": "Widget",
            "sku": "SKU-1",
            "growth_pct": 20.0,
            "history_total_units": 500,
            "forecast_total_units": 600,
            "model_used": "holt_linear",
            "wape": 10.0,
            "horizon_periods": 6,
        }
        narrative = provider.generate(context)
        assert "growing" in narrative.headline.lower()
        assert any("increase" in rec.lower() for rec in narrative.recommendations)

    def test_unreliable_forecast_adds_override_recommendation(self) -> None:
        provider = TemplateProvider()
        context = {
            "scope": "product",
            "product_name": "Widget",
            "wape": 55.0,
            "history_total_units": 100,
        }
        narrative = provider.generate(context)
        assert any("override" in rec.lower() for rec in narrative.recommendations)


class TestTemplateProviderException:
    def test_summarises_single_exception(self) -> None:
        provider = TemplateProvider()
        context = {
            "scope": "exception",
            "exception": {
                "title": "Stockout risk on Widget",
                "message": "Stock covers 0.2 periods.",
                "recommendation": "Expedite replenishment.",
                "severity": "critical",
            },
        }
        narrative = provider.generate(context)
        assert narrative.headline == "Stockout risk on Widget"
        assert "Expedite replenishment." in narrative.recommendations


class TestInsightServiceFailover:
    def test_falls_back_when_primary_raises(self) -> None:
        service = InsightService(primary=FailingProvider(), fallback=TemplateProvider(), ai_enabled=True)
        narrative = service.generate({"scope": "portfolio", "product_count": 1})
        assert narrative.generated_by == "template"

    def test_uses_primary_when_it_succeeds(self) -> None:
        stub_narrative = Narrative(headline="ok", summary="fine", generated_by="stub")
        service = InsightService(
            primary=StubProvider(stub_narrative), fallback=TemplateProvider(), ai_enabled=True
        )
        narrative = service.generate({"scope": "portfolio"})
        assert narrative.generated_by == "stub"

    def test_ai_disabled_skips_primary_entirely(self) -> None:
        service = InsightService(primary=FailingProvider(), fallback=TemplateProvider(), ai_enabled=False)
        narrative = service.generate({"scope": "portfolio", "product_count": 1})
        assert narrative.generated_by == "template"


class TestParseNarrativeJson:
    """Covers the JSON-extraction logic shared by every LLM provider."""

    def test_parses_clean_json(self) -> None:
        narrative = _parse_narrative_json(
            '{"headline": "Growth ahead", "summary": "Demand is up.", '
            '"recommendations": ["Order more stock."]}',
            provider_name="ollama",
            model_name="llama3.1",
        )
        assert narrative.headline == "Growth ahead"
        assert narrative.recommendations == ["Order more stock."]
        assert narrative.generated_by == "ollama"
        assert narrative.model_name == "llama3.1"

    def test_strips_prose_wrapper_around_json(self) -> None:
        raw = 'Sure, here you go:\n{"headline": "H", "summary": "S", "recommendations": []}\nHope that helps!'
        narrative = _parse_narrative_json(raw, provider_name="groq", model_name="m")
        assert narrative.headline == "H"
        assert narrative.summary == "S"

    def test_missing_summary_raises(self) -> None:
        with pytest.raises(ValueError):
            _parse_narrative_json('{"headline": "H"}', provider_name="ollama", model_name="m")

    def test_empty_response_raises(self) -> None:
        with pytest.raises(ValueError):
            _parse_narrative_json("", provider_name="ollama", model_name="m")

    def test_single_string_recommendation_is_wrapped_in_a_list(self) -> None:
        narrative = _parse_narrative_json(
            '{"headline": "H", "summary": "S", "recommendations": "Just one."}',
            provider_name="groq",
            model_name="m",
        )
        assert narrative.recommendations == ["Just one."]

    def test_headline_over_90_chars_is_truncated(self) -> None:
        long_headline = "H" * 150
        narrative = _parse_narrative_json(
            f'{{"headline": "{long_headline}", "summary": "S"}}',
            provider_name="ollama",
            model_name="m",
        )
        assert len(narrative.headline) == 90


class TestGroqProvider:
    def test_requires_an_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.core.config import settings

        # GroqProvider(api_key=None) falls back to settings.groq_api_key, so a
        # developer's real local key (in backend/.env) must not leak into this
        # "no key configured" test — force the setting to None explicitly.
        monkeypatch.setattr(settings, "groq_api_key", None)
        provider = GroqProvider(api_key=None)
        with pytest.raises(ValueError, match="GROQ_API_KEY"):
            provider.generate({"scope": "portfolio"})

    def test_sends_bearer_auth_and_json_mode(self) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["auth"] = request.headers.get("authorization")
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": '{"headline": "H", "summary": "S", "recommendations": []}'
                            }
                        }
                    ]
                },
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        provider = GroqProvider(api_key="test-key", model="openai/gpt-oss-120b", client=client)

        narrative = provider.generate({"scope": "portfolio", "product_count": 5})

        assert narrative.headline == "H"
        assert narrative.generated_by == "groq"
        assert narrative.model_name == "openai/gpt-oss-120b"
        assert captured["auth"] == "Bearer test-key"
        assert captured["url"].endswith("/chat/completions")

    def test_propagates_http_errors_for_insight_service_to_catch(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "invalid api key"})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        provider = GroqProvider(api_key="bad-key", client=client)

        with pytest.raises(httpx.HTTPStatusError):
            provider.generate({"scope": "portfolio"})

    def test_malformed_json_content_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, json={"choices": [{"message": {"content": "not valid json"}}]}
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        provider = GroqProvider(api_key="test-key", client=client)

        with pytest.raises(json.JSONDecodeError):
            provider.generate({"scope": "portfolio"})


class TestBuildDefaultPrimary:
    def test_ollama_is_the_default(self) -> None:
        assert isinstance(_build_default_primary("ollama"), OllamaProvider)

    def test_groq_selects_groq_provider(self) -> None:
        assert isinstance(_build_default_primary("groq"), GroqProvider)


class TestInsightServiceProviderSelection:
    def test_ai_provider_setting_selects_groq(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.core.config import settings

        monkeypatch.setattr(settings, "ai_provider", "groq")
        service = InsightService(ai_enabled=True)
        assert isinstance(service.primary, GroqProvider)

    def test_ai_provider_setting_selects_ollama_by_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.core.config import settings

        monkeypatch.setattr(settings, "ai_provider", "ollama")
        service = InsightService(ai_enabled=True)
        assert isinstance(service.primary, OllamaProvider)

    def test_groq_failure_falls_back_to_template(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.core.config import settings

        monkeypatch.setattr(settings, "groq_api_key", None)
        service = InsightService(
            primary=GroqProvider(api_key=None), fallback=TemplateProvider(), ai_enabled=True
        )
        narrative = service.generate({"scope": "portfolio", "product_count": 3})
        assert narrative.generated_by == "template"
