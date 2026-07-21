"""Shared multi-provider LLM plumbing: client management, schema-enforced
calls, JSON recovery, and the repair-turn mechanism.

Extracted out of classifier.py once a second consumer (feedback_ai.py, the
PM insights pipeline) needed the exact same reliability behavior — same
three providers, same strict-JSON-Schema enforcement, same
parse/validate/repair/fallback shape. Everything here is deliberately
schema- and prompt-agnostic (callers pass their own system prompt + JSON
Schema); only the *shape* of "call a provider, get JSON back, recover if it
isn't" lives here. Each pipeline still owns its own prompt, schema, Pydantic
model, and fallback behavior.
"""
import json
import os
import re

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-8")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
FORCE_MOCK = os.environ.get("FORCE_MOCK_MODE", "").strip().lower() in ("1", "true", "yes")

PROVIDER_MODEL = {"anthropic": MODEL, "openai": OPENAI_MODEL, "groq": GROQ_MODEL}
# Preference order when only one provider's answer is needed: Anthropic and
# OpenAI both get a strict JSON Schema enforced by the API; Groq only gets
# JSON mode, so it's the weakest guarantee and goes last.
PROVIDER_PRIORITY = ["anthropic", "openai", "groq"]

REPAIR_INSTRUCTION = (
    "Your previous response could not be parsed as valid JSON matching the required schema. "
    "Respond again with ONLY a single JSON object matching the schema — no markdown fences, "
    "no commentary, no trailing text."
)

_clients: dict[str, object] = {}
_unavailable_reasons: dict[str, str] = {}


def _build_client(provider: str):
    """Construct and validate credentials for a single provider. Returns the
    client, or None (recording why in _unavailable_reasons) if that provider
    isn't configured."""
    try:
        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic()
            if not (client.api_key or client.auth_token):
                _unavailable_reasons[provider] = "ANTHROPIC_API_KEY not set"
                return None
            return client
        if provider == "openai":
            import openai
            return openai.OpenAI()
        if provider == "groq":
            import groq
            return groq.Groq()
    except Exception as exc:  # pragma: no cover - environment dependent
        _unavailable_reasons[provider] = str(exc)
        return None
    return None


def get_client(provider: str):
    if FORCE_MOCK:
        return None
    if provider not in _clients:
        _clients[provider] = _build_client(provider)
    return _clients[provider]


def available_providers() -> list[str]:
    """All providers with usable credentials, in preference order."""
    return [p for p in PROVIDER_PRIORITY if get_client(p) is not None]


def mode_info() -> dict:
    providers = available_providers()
    live = len(providers) > 0
    primary = providers[0] if providers else None
    if live:
        reason = None
    elif FORCE_MOCK:
        reason = "FORCE_MOCK_MODE is enabled"
    else:
        reason = next(iter(_unavailable_reasons.values()), None) or (
            "no ANTHROPIC_API_KEY, OPENAI_API_KEY, or GROQ_API_KEY set"
        )
    return {
        "mode": "live" if live else "mock",
        "provider": primary,
        "providers_available": providers,
        "model": PROVIDER_MODEL.get(primary, "keyword-baseline"),
        "forced_mock": FORCE_MOCK,
        "reason": reason,
    }


def extract_json(text: str) -> dict | None:
    """Best-effort recovery of a JSON object from a (possibly messy) string.
    Used both as defense-in-depth on real responses and by the /demo repair
    endpoint to show the mechanism deterministically."""
    text = text.strip()
    # Strip ```json ... ``` or ``` ... ``` fences if present.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Grab the first {...} block and try again (handles stray prose around it).
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    candidate = match.group(0)
    # Common LLM-ism: trailing comma before a closing brace/bracket.
    candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def call_anthropic(client, message: str, system_prompt: str, schema: dict, repair: bool, prior_content=None):
    kwargs = dict(
        model=MODEL,
        max_tokens=1024,
        system=system_prompt,
        output_config={"format": {"type": "json_schema", "schema": schema}, "effort": "low"},
    )
    if repair and prior_content is not None:
        kwargs["messages"] = [
            {"role": "user", "content": message},
            {"role": "assistant", "content": prior_content},
            {"role": "user", "content": REPAIR_INSTRUCTION},
        ]
    else:
        kwargs["messages"] = [{"role": "user", "content": message}]
    return client.messages.create(**kwargs)


def call_openai(client, message: str, system_prompt: str, schema: dict, repair: bool, prior_text: str | None = None):
    """OpenAI's chat.completions API with strict Structured Outputs — like
    Claude, the schema itself is enforced by the API, not just requested."""
    messages = [{"role": "system", "content": system_prompt}]
    if repair and prior_text is not None:
        messages += [
            {"role": "user", "content": message},
            {"role": "assistant", "content": prior_text},
            {"role": "user", "content": REPAIR_INSTRUCTION},
        ]
    else:
        messages.append({"role": "user", "content": message})
    return client.chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=1024,
        messages=messages,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "structured_response", "schema": schema, "strict": True},
        },
    )


def call_groq(client, message: str, system_prompt: str, schema: dict, repair: bool, prior_text: str | None = None):
    """Groq's chat.completions API — OpenAI-shaped, not Claude's Messages API.
    Requests JSON mode rather than a strict schema (Groq's schema enforcement
    is weaker/model-dependent), and leans on the shared extract_json +
    Pydantic validation + repair turn to cover the gap. Groq's JSON mode only
    guarantees syntactically valid JSON, not conformance to `schema` — and
    requires the word "json" somewhere in the messages — so the schema is
    spelled out in the prompt itself here, unlike Claude/OpenAI.
    """
    groq_system_prompt = (
        system_prompt
        + "\n\nRespond with ONLY a single JSON object matching this schema, no markdown fences, "
        "no commentary:\n" + json.dumps(schema)
    )
    messages = [{"role": "system", "content": groq_system_prompt}]
    if repair and prior_text is not None:
        messages += [
            {"role": "user", "content": message},
            {"role": "assistant", "content": prior_text},
            {"role": "user", "content": REPAIR_INSTRUCTION},
        ]
    else:
        messages.append({"role": "user", "content": message})
    return client.chat.completions.create(
        model=GROQ_MODEL,
        max_tokens=1024,
        messages=messages,
        response_format={"type": "json_object"},
    )


def transient_errors_for(provider: str):
    if provider == "anthropic":
        import anthropic
        return (anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.APIStatusError)
    if provider == "openai":
        import openai
        return (openai.APIConnectionError, openai.RateLimitError, openai.APIStatusError)
    import groq
    return (groq.APIConnectionError, groq.RateLimitError, groq.APIStatusError)
