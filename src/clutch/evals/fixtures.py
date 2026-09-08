"""Validated loading for versioned JSON evaluation fixtures."""

import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

CaseT = TypeVar("CaseT", bound=BaseModel)


def load_cases(path: Path, model_type: type[CaseT]) -> list[CaseT]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"eval fixture must contain a JSON list: {path}")
    return [model_type.model_validate(item) for item in payload]
