from typing import Optional

from pydantic import BaseModel, ConfigDict

from ..enums.domain import Domain


class GlobalState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: Optional[Domain] = None
