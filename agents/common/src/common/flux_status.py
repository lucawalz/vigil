from __future__ import annotations

import re


def parse_kust_text(text: str) -> dict:
    m = re.search(r"^\s*Ready:\s*([A-Za-z]+)(?:\s+-\s*(.*))?$", text, re.MULTILINE)
    if m:
        return {
            "ready": m.group(1),
            "reason": (m.group(2) or "").strip(),
            "message": "",
        }
    return {"ready": "Unknown", "reason": "parse_error", "message": text[:200]}


def extract_mcp_text(result: object) -> str:
    if isinstance(result, dict) and "content" in result:
        return str(result["content"])
    return str(result)
