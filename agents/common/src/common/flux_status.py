from __future__ import annotations

import json

_ENVELOPE_KEYS = ("content", "text", "result")


def coerce_flux_status(result: object) -> dict:
    """Normalise a flux-mcp status tool result into its structured dict.

    flux-mcp returns kustomization and gitrepository status as a JSON object
    carrying a ``found`` field. Callers may receive it already decoded as a
    dict, as a JSON string, or wrapped in an MCP envelope (``{"content": ...}``);
    all three are accepted.
    """
    payload: object = result
    if isinstance(payload, dict) and "found" not in payload:
        for key in _ENVELOPE_KEYS:
            if key in payload:
                payload = payload[key]
                break
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"flux status not JSON-decodable: {payload[:120]}"
            ) from exc
    if not isinstance(payload, dict):
        raise ValueError("flux status missing structured fields")
    return payload
