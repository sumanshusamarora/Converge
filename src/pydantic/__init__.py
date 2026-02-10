"""Lightweight subset of the pydantic API used for offline tests."""

from __future__ import annotations

import json
from dataclasses import MISSING
from typing import Any


class FieldInfo:
    """Container for default values declared with ``Field``."""

    def __init__(self, default: Any = MISSING, default_factory: Any = None) -> None:
        self.default = default
        self.default_factory = default_factory


def Field(*, default: Any = MISSING, default_factory: Any = None) -> FieldInfo:
    """Declare model field defaults."""
    return FieldInfo(default=default, default_factory=default_factory)


class BaseModel:
    """Minimal BaseModel compatible with this repository's usage."""

    def __init__(self, **data: Any) -> None:
        annotations = getattr(self, "__annotations__", {})
        for field_name in annotations:
            if field_name in data:
                value = data[field_name]
            else:
                class_default = getattr(type(self), field_name, MISSING)
                if isinstance(class_default, FieldInfo):
                    if class_default.default_factory is not None:
                        value = class_default.default_factory()
                    elif class_default.default is not MISSING:
                        value = class_default.default
                    else:
                        raise ValueError(f"Missing required field: {field_name}")
                elif class_default is not MISSING:
                    value = class_default
                else:
                    raise ValueError(f"Missing required field: {field_name}")
            setattr(self, field_name, value)

    @classmethod
    def model_validate(cls, payload: dict[str, Any]) -> Any:
        """Validate a dictionary payload into a model instance."""
        return cls(**payload)

    def model_dump(self) -> dict[str, Any]:
        """Serialize model to a dictionary."""
        result: dict[str, Any] = {}
        annotations = getattr(self, "__annotations__", {})
        for field_name in annotations:
            value = getattr(self, field_name)
            if isinstance(value, BaseModel):
                result[field_name] = value.model_dump()
            else:
                result[field_name] = value
        return result

    def model_dump_json(self) -> str:
        """Serialize model to JSON."""
        return json.dumps(self.model_dump(), default=str)
