from pydantic import BaseModel, ConfigDict


class AssistantResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
