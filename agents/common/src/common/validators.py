"""Shared pydantic helpers for normalising LLM-produced model input."""

from types import NoneType
from typing import Any, get_args, get_origin

from pydantic import BaseModel

_NULL_SENTINELS = frozenset({"none", "null", "nil", ""})

_nullable_fields_cache: dict[type[BaseModel], frozenset[str]] = {}


def _annotation_permits_none(annotation: Any) -> bool:
    if get_origin(annotation) is None:
        return annotation is NoneType
    return any(_annotation_permits_none(arg) for arg in get_args(annotation))


def _nullable_field_names(model_cls: type[BaseModel]) -> frozenset[str]:
    cached = _nullable_fields_cache.get(model_cls)
    if cached is not None:
        return cached
    names = frozenset(
        name
        for name, field in model_cls.model_fields.items()
        if _annotation_permits_none(field.annotation)
    )
    _nullable_fields_cache[model_cls] = names
    return names


def normalize_enum(value: Any) -> Any:
    """Strip and lowercase a string enum value; leave non-strings untouched.

    LLMs occasionally emit enum members with stray case or whitespace (e.g.
    "High "); normalising only case/whitespace avoids a wasted validation retry
    while still rejecting genuinely unknown members.
    """
    if isinstance(value, str):
        return value.strip().lower()
    return value


def coerce_null_sentinels(model_cls: type[BaseModel], data: Any) -> Any:
    """Replace null-sentinel strings with None on nullable fields only.

    LLMs occasionally emit the literal string "None"/"null" for a nullable
    output field; pydantic rejects it and triggers an expensive validation
    retry. Coercion is deliberately narrow — it never touches non-nullable
    fields or non-string values, so genuinely malformed output still fails.
    """
    if not isinstance(data, dict):
        return data
    nullable = _nullable_field_names(model_cls)
    return {
        key: None
        if (
            key in nullable
            and isinstance(value, str)
            and value.strip().lower() in _NULL_SENTINELS
        )
        else value
        for key, value in data.items()
    }
