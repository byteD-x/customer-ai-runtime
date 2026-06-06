from __future__ import annotations

from customer_ai_runtime.core.config import Settings
from customer_ai_runtime.domain.models import (
    BusinessResult,
    Citation,
    LLMRequest,
    Message,
    MessageRole,
    RouteType,
)
from customer_ai_runtime.providers.openai_provider import OpenAILLMProvider, _build_prompt


def test_openai_prompt_is_redacted_and_bounded() -> None:
    request = LLMRequest(
        tenant_id="demo-tenant",
        session_id="session_demo",
        route=RouteType.KNOWLEDGE,
        user_message="我的邮箱是 test@example.com，token=sk-12345678，请帮我查一下。",
        history=[
            Message(role=MessageRole.USER, content="手机号 13800138000，password=abc"),
            Message(role=MessageRole.ASSISTANT, content="好的，我会处理 sk-ABCDEFGH1234"),
        ],
        citations=[
            Citation(
                knowledge_base_id="kb_support",
                document_id="doc_1",
                title="t",
                chunk_id="chunk_1",
                score=0.9,
                excerpt="联系邮箱 test@example.com",
            )
        ],
        tool_result=BusinessResult(
            tool_name="order_status",
            status="ok",
            summary="ok",
            data={"api_key": "sk-12345678", "password": "abc", "note": "call me 13800138000"},
        ),
        prompt_template="TEMPLATE",
        structured_schema={
            "type": "object",
            "properties": {"api_key": {"const": "sk-12345678"}},
        },
    )

    prompt = _build_prompt(request)

    # Raw secrets should not appear.
    assert "test@example.com" not in prompt
    assert "13800138000" not in prompt
    assert "sk-12345678" not in prompt

    # Redacted markers should appear.
    assert "sk-***" in prompt
    assert "***@example.com" in prompt
    assert "138****8000" in prompt
    assert "***" in prompt

    assert len(prompt) <= 4000


async def test_openai_provider_allows_request_model_override() -> None:
    class FakeResponses:
        def __init__(self) -> None:
            self.model = ""

        async def create(self, *, model: str, input: str):  # noqa: A002
            self.model = model
            return type(
                "FakeResponse",
                (),
                {
                    "output_text": "ok",
                    "usage": type(
                        "FakeUsage",
                        (),
                        {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5},
                    )(),
                },
            )()

    class FakeClient:
        def __init__(self) -> None:
            self.responses = FakeResponses()

    provider = OpenAILLMProvider(Settings(openai_api_key="test-key"))
    fake_client = FakeClient()
    provider._client = fake_client

    response = await provider.generate(
        LLMRequest(
            tenant_id="demo-tenant",
            session_id="session_demo",
            route=RouteType.FALLBACK,
            user_message="hello",
            prompt_template="answer shortly",
            model="gpt-test-override",
        )
    )

    assert fake_client.responses.model == "gpt-test-override"
    assert response.answer == "ok"
    assert response.usage is not None
    assert response.usage.total_tokens == 5
