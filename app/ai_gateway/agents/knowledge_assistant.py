from agents import Agent

from app.ai_gateway.schemas import AssistantResponse
from app.config import settings


def build_knowledge_assistant() -> Agent[None]:
    return Agent(
        name="SkyKnow Knowledge Assistant",
        instructions=(
            "You are SkyKnow's assistant. Give clear, concise, and helpful "
            "answers based only on information provided in the conversation. "
            "Do not claim to search or access SkyKnow's internal knowledge "
            "base; no knowledge-search tools are connected yet. If a request "
            "depends on internal company information, say that you cannot "
            "verify it from the available context."
        ),
        model=settings.AI_DEFAULT_MODEL,
        output_type=AssistantResponse,
    )
