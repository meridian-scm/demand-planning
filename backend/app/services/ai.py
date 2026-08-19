"""AI narrative layer.

Turns the numeric outputs of the forecast engine and the exception detector
into business-readable summaries and recommendations.

Three providers are supported:

``OllamaProvider``
    Calls a locally-hosted Llama 3.1 through Ollama's ``/api/generate``
    endpoint. Used when ``AI_PROVIDER=ollama`` (the default) and the daemon
    is reachable.

``GroqProvider``
    Calls a hosted model on Groq's OpenAI-compatible chat-completions API.
    Used when ``AI_PROVIDER=groq`` and ``GROQ_API_KEY`` is set. No local
    daemon required — this is the faster path if you have a Groq API key.

``TemplateProvider``
    A deterministic, dependency-free narrator. It is the fallback whenever the
    configured LLM provider is unavailable or misconfigured, and it is what
    the test suite runs against so tests never depend on a model or network
    access being available.

The service always returns a narrative — an unreachable/misconfigured LLM
degrades the wording, never the availability of the planning workflow. Every
response records ``generated_by`` so the UI can label AI-written text
honestly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are a supply chain demand planning assistant. You write for demand "
    "planners and supply chain managers. Be concise, specific and quantitative. "
    "Never invent numbers that are not in the provided data. Respond ONLY with "
    "valid JSON matching this schema: "
    '{"headline": string, "summary": string, "recommendations": [string, ...]}. '
    "The headline is at most 90 characters. The summary is 2-4 sentences. "
    "Provide 2 to 4 recommendations, each a single actionable sentence."
)


@dataclass(slots=True)
class Narrative:
    """A generated insight, plus provenance."""

    headline: str
    summary: str
    recommendations: list[str] = field(default_factory=list)
    generated_by: str = "fallback"
    model_name: str | None = None


class InsightProvider(Protocol):
    """Anything that can turn a structured planning context into prose."""

    name: str

    def generate(self, context: dict) -> Narrative: ...


def _build_prompt(context: dict) -> str:
    """The user-turn prompt shared by every LLM provider — only the transport differs."""
    scope = context.get("scope", "portfolio")
    instruction = {
        "product": "Summarise the demand outlook for this single product.",
        "exception": "Explain this planning exception and what the planner should do.",
        "portfolio": "Summarise the demand planning position across the portfolio.",
    }.get(scope, "Summarise the demand planning position.")

    return (
        f"{instruction}\n\nPlanning data (JSON):\n"
        f"{json.dumps(context, default=str, indent=2)}\n\n"
        "Respond with JSON only."
    )


def _parse_narrative_json(raw: str, *, provider_name: str, model_name: str) -> Narrative:
    """Parse an LLM's JSON reply into a Narrative, tolerating a prose wrapper.

    Shared by every LLM provider: each is instructed to return only JSON, but
    models routinely wrap it in a sentence or markdown fence anyway, so this
    extracts the outermost ``{...}`` before decoding rather than trusting the
    response to be clean.
    """
    text = raw.strip()
    if not text:
        raise ValueError(f"empty response from {provider_name}")

    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        text = text[start : end + 1]

    data = json.loads(text)
    recommendations = data.get("recommendations") or []
    if isinstance(recommendations, str):
        recommendations = [recommendations]

    headline = str(data.get("headline") or "Demand planning insight").strip()
    summary = str(data.get("summary") or "").strip()
    if not summary:
        raise ValueError(f"{provider_name} response contained no summary")

    return Narrative(
        headline=headline[:90],
        summary=summary,
        recommendations=[str(item).strip() for item in recommendations][:4],
        generated_by=provider_name,
        model_name=model_name,
    )


# --------------------------------------------------------------------------- #
# Deterministic fallback
# --------------------------------------------------------------------------- #
class TemplateProvider:
    """Rule-based narrator used when no LLM is available.

    Deliberately boring and fully deterministic: the same context always yields
    the same text, which is what makes it usable as a test oracle.
    """

    name = "template"

    def generate(self, context: dict) -> Narrative:
        scope = context.get("scope", "portfolio")
        if scope == "product":
            return self._product(context)
        if scope == "exception":
            return self._exception(context)
        return self._portfolio(context)

    # -- scope: product ------------------------------------------------- #
    def _product(self, context: dict) -> Narrative:
        name = context.get("product_name", "This product")
        sku = context.get("sku", "")
        history_total = float(context.get("history_total_units") or 0)
        forecast_total = float(context.get("forecast_total_units") or 0)
        growth = context.get("growth_pct")
        model = context.get("model_used", "the selected model")
        wape = context.get("wape")
        horizon = int(context.get("horizon_periods") or 0)
        exceptions = context.get("exceptions") or []

        direction = "steady"
        if isinstance(growth, int | float):
            if growth >= 5:
                direction = "growing"
            elif growth <= -5:
                direction = "declining"

        headline = f"{name} demand is {direction}"
        if isinstance(growth, int | float):
            headline += f" ({growth:+.1f}%)"

        summary_parts = [
            f"{name}{f' ({sku})' if sku else ''} recorded {history_total:,.0f} units of demand "
            f"over its recent history."
        ]
        if horizon:
            summary_parts.append(
                f"The {model} model projects {forecast_total:,.0f} units across the next "
                f"{horizon} periods."
            )
        if isinstance(wape, int | float):
            quality = "reliable" if wape <= 20 else "usable with caution" if wape <= 40 else "weak"
            summary_parts.append(f"Backtest accuracy is {wape:.1f}% WAPE, which is {quality}.")
        if exceptions:
            summary_parts.append(
                f"{len(exceptions)} open planning exception(s) are attached to this product."
            )

        recommendations: list[str] = []
        if direction == "growing":
            recommendations.append(
                "Increase replenishment quantities and confirm supplier capacity can support the "
                "higher run rate."
            )
        elif direction == "declining":
            recommendations.append(
                "Reduce open purchase orders and review whether current stock will age before it "
                "sells."
            )
        else:
            recommendations.append(
                "Hold the current replenishment plan and continue monitoring at the normal cadence."
            )
        if isinstance(wape, int | float) and wape > 40:
            recommendations.append(
                "Apply a planner override for this SKU — the statistical forecast is not reliable "
                "enough to run unadjusted."
            )
        for item in exceptions[:2]:
            rec = item.get("recommendation")
            if rec:
                recommendations.append(rec)
        if len(recommendations) < 2:
            recommendations.append(
                "Review the forecast against commercial input before locking the plan."
            )

        return Narrative(
            headline=headline[:90],
            summary=" ".join(summary_parts),
            recommendations=recommendations[:4],
            generated_by=self.name,
        )

    # -- scope: exception ----------------------------------------------- #
    def _exception(self, context: dict) -> Narrative:
        exc = context.get("exception", {})
        title = exc.get("title", "Planning exception")
        message = exc.get("message", "")
        recommendation = exc.get("recommendation")
        severity = exc.get("severity", "medium")

        return Narrative(
            headline=title[:90],
            summary=f"{message} Severity is rated {severity}.".strip(),
            recommendations=[recommendation] if recommendation else ["Review this exception."],
            generated_by=self.name,
        )

    # -- scope: portfolio ----------------------------------------------- #
    def _portfolio(self, context: dict) -> Narrative:
        products = int(context.get("product_count") or 0)
        forecast_total = float(context.get("forecast_total_units") or 0)
        history_total = float(context.get("history_total_units") or 0)
        growth = context.get("growth_pct")
        open_exceptions = int(context.get("open_exception_count") or 0)
        critical = int(context.get("critical_exception_count") or 0)
        top_growing = context.get("top_growing") or []
        top_declining = context.get("top_declining") or []

        headline = f"{products} products planned, {open_exceptions} open exceptions"

        summary_parts = [
            f"The portfolio covers {products} active products with {history_total:,.0f} units of "
            f"recent demand and {forecast_total:,.0f} units forecast for the planning horizon."
        ]
        if isinstance(growth, int | float):
            summary_parts.append(f"Overall demand is trending {growth:+.1f}% period over period.")
        if open_exceptions:
            summary_parts.append(
                f"{open_exceptions} exceptions are open, of which {critical} are critical."
            )
        else:
            summary_parts.append("No planning exceptions are currently open.")

        recommendations: list[str] = []
        if critical:
            recommendations.append(
                f"Work the {critical} critical exception(s) first — these carry the highest "
                "service risk this cycle."
            )
        if top_growing:
            names = ", ".join(str(item) for item in top_growing[:3])
            recommendations.append(
                f"Secure additional supply for the fastest-growing products: {names}."
            )
        if top_declining:
            names = ", ".join(str(item) for item in top_declining[:3])
            recommendations.append(
                f"Reduce replenishment and review stock cover on declining products: {names}."
            )
        if len(recommendations) < 2:
            recommendations.append(
                "Maintain the current plan and re-run the forecast when the next period closes."
            )

        return Narrative(
            headline=headline[:90],
            summary=" ".join(summary_parts),
            recommendations=recommendations[:4],
            generated_by=self.name,
        )


# --------------------------------------------------------------------------- #
# Ollama / Llama 3.1
# --------------------------------------------------------------------------- #
class OllamaProvider:
    """Generates narratives with a locally-hosted Llama 3.1 via Ollama."""

    name = "ollama"

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.timeout = timeout or settings.ollama_timeout_seconds
        self._client = client

    def is_available(self) -> bool:
        """Cheap reachability probe so a dead daemon does not stall requests."""
        try:
            client = self._client or httpx.Client(timeout=2.0)
            response = client.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except Exception as exc:  # noqa: BLE001 - availability probe must never raise
            logger.debug("ollama probe failed: %s", exc)
            return False

    def generate(self, context: dict) -> Narrative:
        payload = {
            "model": self.model,
            "prompt": _build_prompt(context),
            "system": _SYSTEM_PROMPT,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2},
        }

        client = self._client or httpx.Client(timeout=self.timeout)
        response = client.post(f"{self.base_url}/api/generate", json=payload)
        response.raise_for_status()
        body = response.json()
        return _parse_narrative_json(
            body.get("response", ""), provider_name=self.name, model_name=self.model
        )


# --------------------------------------------------------------------------- #
# Groq (hosted, OpenAI-compatible chat completions)
# --------------------------------------------------------------------------- #
class GroqProvider:
    """Generates narratives via a hosted model on Groq's chat-completions API.

    No local daemon needed — just an API key. Groq's API is OpenAI-compatible,
    so this is a plain ``httpx`` POST rather than a dedicated SDK dependency,
    matching how :class:`OllamaProvider` is implemented.
    """

    name = "groq"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key or settings.groq_api_key
        self.base_url = (base_url or settings.groq_base_url).rstrip("/")
        self.model = model or settings.groq_model
        self.timeout = timeout or settings.groq_timeout_seconds
        self._client = client

    def generate(self, context: dict) -> Narrative:
        if not self.api_key:
            # Fails fast into InsightService's fallback rather than sending an
            # unauthenticated request that Groq would reject anyway.
            raise ValueError("GROQ_API_KEY is not configured")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_prompt(context)},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}

        client = self._client or httpx.Client(timeout=self.timeout)
        response = client.post(
            f"{self.base_url}/chat/completions", json=payload, headers=headers
        )
        response.raise_for_status()
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        return _parse_narrative_json(content, provider_name=self.name, model_name=self.model)


# --------------------------------------------------------------------------- #
# Facade
# --------------------------------------------------------------------------- #
def _build_default_primary(provider_name: str) -> InsightProvider:
    """Construct the configured LLM provider (``AI_PROVIDER=ollama|groq``)."""
    if provider_name == "groq":
        return GroqProvider()
    return OllamaProvider()


class InsightService:
    """Chooses a provider and guarantees a narrative comes back."""

    def __init__(
        self,
        primary: InsightProvider | None = None,
        fallback: InsightProvider | None = None,
        *,
        ai_enabled: bool | None = None,
    ) -> None:
        self.ai_enabled = settings.ai_enabled if ai_enabled is None else ai_enabled
        self.primary = (
            primary
            if primary is not None
            else (_build_default_primary(settings.ai_provider) if self.ai_enabled else None)
        )
        self.fallback = fallback or TemplateProvider()

    def generate(self, context: dict) -> Narrative:
        """Generate a narrative, degrading to the template provider on any failure."""
        if self.ai_enabled and self.primary is not None:
            try:
                return self.primary.generate(context)
            except Exception as exc:  # noqa: BLE001 - any provider failure degrades
                if not settings.ai_fallback_enabled:
                    raise
                logger.warning(
                    "AI provider %s failed (%s); using deterministic fallback",
                    getattr(self.primary, "name", "unknown"),
                    exc,
                )
        return self.fallback.generate(context)
