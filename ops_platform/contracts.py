"""Strict input contracts shared by domain records."""
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Identifier = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$")]
Count = Annotated[int, Field(strict=True, ge=0, le=1_000_000_000)]
Positive = Annotated[int, Field(strict=True, ge=1, le=1_000_000_000)]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


def unique(values, label):
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")
