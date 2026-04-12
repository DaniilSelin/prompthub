from prompthub.core.tokenizers.openai_tag import OpenAIModelTag
from prompthub.facade.storage import Storage
from prompthub.infrastructure.pricing_gateway import OpenRouterPricingGateway


def run_demo() -> None:
    """Локальный smoke-demo для ручной проверки основных сценариев."""
    storage = Storage(":memory:")

    prompt = storage.create_prompt("demo_prompt", author="demo")
    prompt.add_version(
        content=[("system", "You are concise."), ("user", "Say hello")],
        description="initial",
    )

    storage.add_prompt_tag("demo_prompt", "demo")
    storage.add_model_tags("demo_prompt", [OpenAIModelTag("gpt-4o")])

    raw = storage.fetch_prompt("demo_prompt")
    as_openai = storage.fetch_prompt("demo_prompt", adapter_type="openai")

    print("RAW:", raw)
    print("OPENAI:", as_openai)
    print("LIST:", storage.list_prompts())

    # Сетевой вызов оставляем опциональным: при ошибке выводим предупреждение.
    try:
        gateway = OpenRouterPricingGateway()
        storage.update_tariffs(gateway)
        print("Tariffs updated")
    except Exception as exc:
        print(f"Tariffs update skipped: {exc}")


if __name__ == "__main__":
    run_demo()
