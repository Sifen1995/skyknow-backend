from agents import Runner, set_default_openai_key

from app.ai_gateway.agents import build_knowledge_assistant
from app.ai_gateway.schemas import AssistantResponse
from app.config import settings


async def run_knowledge_assistant(prompt: str) -> AssistantResponse:
    if settings.OPENAI_API_KEY is None:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    set_default_openai_key(
        settings.OPENAI_API_KEY.get_secret_value(),
        use_for_tracing=False,
    )
    result = await Runner.run(
        build_knowledge_assistant(),
        input=prompt,
    )
    if not isinstance(result.final_output, AssistantResponse):
        raise TypeError("Knowledge assistant returned an unexpected output type")
    return result.final_output
