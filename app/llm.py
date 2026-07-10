from collections.abc import Callable

from langchain_core.language_models import BaseChatModel

from app.config import Settings, get_settings


def _require_key(value: str, name: str) -> None:
    if not value:
        raise ValueError(
            f"{name} is not set. "
            "Add it to your .env file or environment before starting the service."
        )


def _build_anthropic(settings: Settings) -> BaseChatModel:
    _require_key(settings.anthropic_api_key, "ANTHROPIC_API_KEY")
    from langchain_anthropic import ChatAnthropic  # noqa: PLC0415

    return ChatAnthropic(
        model=settings.anthropic_model,
        anthropic_api_key=settings.anthropic_api_key,
    )


def _build_google(settings: Settings) -> BaseChatModel:
    _require_key(settings.google_api_key, "GOOGLE_API_KEY")
    from langchain_google_genai import ChatGoogleGenerativeAI  # noqa: PLC0415

    return ChatGoogleGenerativeAI(
        model=settings.google_model,
        google_api_key=settings.google_api_key,
    )


_PROVIDERS: dict[str, Callable[[Settings], BaseChatModel]] = {
    "anthropic": _build_anthropic,
    "google": _build_google,
}


def get_chat_model() -> BaseChatModel:
    settings = get_settings()
    builder = _PROVIDERS.get(settings.llm_provider)
    if builder is None:
        raise ValueError(
            f"Unknown LLM_PROVIDER {settings.llm_provider!r}. "
            f"Supported providers: {', '.join(sorted(_PROVIDERS))}"
        )
    return builder(settings)
