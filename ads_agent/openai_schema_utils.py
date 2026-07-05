"""Shared helper for using Pydantic models as OpenAI strict structured outputs."""

from __future__ import annotations


def to_openai_strict_schema(schema: object) -> object:
    """Make a Pydantic-generated JSON schema OpenAI strict-mode compatible.

    OpenAI's strict structured-output mode requires every object's "required"
    array to list *all* of its "properties" keys -- optionality is expressed via
    a nullable type, not by omitting the key. Pydantic's default schema omits
    fields that have a default value, so this walks the schema (including
    $defs for nested models) and fixes each object up in place. It also strips
    sibling keywords (e.g. Pydantic's "default") next to any "$ref", which
    strict mode also forbids.
    """

    if isinstance(schema, dict):
        if "$ref" in schema:
            for key in [k for k in schema if k != "$ref"]:
                del schema[key]
        if schema.get("type") == "object" and "properties" in schema:
            schema["required"] = list(schema["properties"].keys())
            schema["additionalProperties"] = False
        for value in schema.values():
            to_openai_strict_schema(value)
    elif isinstance(schema, list):
        for item in schema:
            to_openai_strict_schema(item)
    return schema
