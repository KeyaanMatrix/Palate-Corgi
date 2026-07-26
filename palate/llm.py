"""Model calls. OWNER D.

Every model call in the pipeline goes through this file, and every call is routed
through Merge Gateway unless LLM_DIRECT=1. That is what makes the Merge claim true
on the critical path (PRD section 11) rather than a bolt-on: the extraction
pipeline does not run without it.

A and B import complete_json / complete_text. Nobody but D edits this file.

If the Gateway misbehaves at 3 AM: set LLM_DIRECT=1 in .env. That is the whole
fallback. Do not start rewriting call sites.
"""

import json
from typing import Any

import anthropic

from . import config, db

_client: anthropic.Anthropic | None = None
_route: str = "direct"


def client() -> anthropic.Anthropic:
    """Anthropic SDK pointed at Merge Gateway, or straight at Anthropic.

    Merge Gateway speaks the Messages API, so it is a base_url swap. If Owner D's
    hour-0 verification shows a different contract, THIS FUNCTION is the only
    thing that changes — every caller keeps working.
    """
    global _client, _route
    if _client is not None:
        return _client

    if config.MERGE_GATEWAY_BASE_URL and not config.LLM_DIRECT:
        _client = anthropic.Anthropic(
            api_key=config.MERGE_GATEWAY_API_KEY or config.ANTHROPIC_API_KEY,
            base_url=config.MERGE_GATEWAY_BASE_URL,
        )
        _route = "gateway"
    else:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        _route = "direct"
    return _client


def route() -> str:
    client()
    return _route


def _call(
    prompt: str,
    *,
    purpose: str,
    max_tokens: int,
    effort: str,
    output_config: dict | None = None,
) -> Any:
    kwargs: dict[str, Any] = {
        "model": config.LLM_MODEL,
        "max_tokens": max_tokens,
        "output_config": {"effort": effort},
        "messages": [{"role": "user", "content": prompt}],
    }
    if output_config:
        kwargs["output_config"].update(output_config)

    try:
        # Streaming: max_tokens is generous and Opus 5 thinks by default, so a
        # non-streaming call risks an HTTP timeout on long extraction batches.
        with client().messages.stream(**kwargs) as stream:
            response = stream.get_final_message()
    except Exception as exc:  # noqa: BLE001 - log and let the caller drop the batch
        db.log_llm_call(purpose, config.LLM_MODEL, route(), ok=False, error=str(exc)[:400])
        raise

    db.log_llm_call(
        purpose,
        config.LLM_MODEL,
        route(),
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
    return response


def _text_of(response: Any) -> str:
    return "".join(b.text for b in response.content if b.type == "text")


def complete_json(
    prompt: str,
    schema: dict,
    *,
    purpose: str,
    max_tokens: int = 8000,
    effort: str = "low",
) -> dict | None:
    """Structured extraction. Returns None on any failure — CALLERS DROP THE ROW.

    Never repair a malformed result (PRD 5.4). Recall is not the constraint
    tonight, precision is.
    """
    try:
        response = _call(
            prompt,
            purpose=purpose,
            max_tokens=max_tokens,
            effort=effort,
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
    except Exception:  # noqa: BLE001
        return None

    if response.stop_reason in ("refusal", "max_tokens"):
        return None
    try:
        return json.loads(_text_of(response))
    except json.JSONDecodeError:
        return None


def complete_text(
    prompt: str,
    *,
    purpose: str,
    max_tokens: int = 2000,
    effort: str = "medium",
) -> str:
    """Prose generation — profile copy, stop rationales."""
    try:
        response = _call(prompt, purpose=purpose, max_tokens=max_tokens, effort=effort)
    except Exception:  # noqa: BLE001
        return ""
    return _text_of(response).strip()


def spend_report() -> str:
    """Token totals by purpose. Check this before the 2 AM full backfill."""
    rows = db.rows(
        "SELECT purpose, route, COUNT(*) n, SUM(input_tokens) i, SUM(output_tokens) o,"
        " SUM(CASE WHEN ok=0 THEN 1 ELSE 0 END) errs"
        " FROM llm_call GROUP BY purpose, route ORDER BY i DESC"
    )
    if not rows:
        return "no model calls logged yet"
    lines = [f"{'purpose':<16}{'route':<10}{'calls':>7}{'in':>10}{'out':>9}{'err':>6}"]
    total_in = total_out = 0
    for r in rows:
        total_in += r["i"] or 0
        total_out += r["o"] or 0
        lines.append(
            f"{r['purpose']:<16}{r['route']:<10}{r['n']:>7}{r['i'] or 0:>10}"
            f"{r['o'] or 0:>9}{r['errs']:>6}"
        )
    # Opus 5 list price: $5/MTok in, $25/MTok out. Rough, but it's the number
    # that tells you whether the $20 Gateway credit survives the backfill.
    est = total_in / 1e6 * 5 + total_out / 1e6 * 25
    lines.append(f"\ntotal in={total_in} out={total_out}  ~${est:.2f} at list price")
    return "\n".join(lines)


COMMANDS = {
    "spend": lambda args: print(spend_report()),
    "route": lambda args: print(f"routing model calls via: {route()}"),
}
