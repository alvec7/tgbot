from __future__ import annotations

from openai import AsyncOpenAI

from src.bot.config import Settings


class OpenAIService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def generate_reply(self, request_text: str, context: list[dict[str, str]]) -> str:
        input_items: list[dict[str, object]] = [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": self.settings.system_prompt}],
            }
        ]

        for message in context:
            input_items.append(
                {
                    "role": message["role"],
                    "content": [{"type": "input_text", "text": message["content"]}],
                }
            )

        input_items.append(
            {
                "role": "user",
                "content": [{"type": "input_text", "text": request_text}],
            }
        )

        try:
            response = await self.client.responses.create(
                model=self.settings.openai_model,
                input=input_items,
            )
        except Exception:
            response = await self.client.responses.create(
                model=self.settings.openai_fallback_model,
                input=input_items,
            )

        return (response.output_text or "").strip()
