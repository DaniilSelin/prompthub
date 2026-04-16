# PromptHub

**Prompt version control system built on SQLite.** Store, version, diff, and roll back LLM prompts - no external services required.

```python
from prompthub import Storage

store = Storage("prompts.db")
prompt = store.create_prompt("my-prompt")
prompt.add_version([("system", "You are helpful."), ("user", "Hello")])
```

## Installation

```bash
pip install prompthub                    # core only - zero dependencies
pip install prompthub[langchain]         # + LangChain adapter
pip install prompthub[openai]            # + OpenAI tokenizer
pip install prompthub[anthropic]         # + Anthropic tokenizer
pip install prompthub[huggingface]       # + HuggingFace tokenizer
pip install prompthub[all]              # everything
```

## Features

- **Version control** - every `add_version()` stores a compact diff (Insert/Delete/Replace operations); full snapshots every N versions
- **Rollback** - soft rollback (new version with old content) or hard rollback (delete history)
- **Diff** - line diff, char diff, structured message diff between any two versions
- **Tags** - label prompts with custom `PromptTag` values; filter with a boolean DSL
- **Token counting & cost estimation** - attach model tags, count tokens, compute cost per 1M tokens from OpenRouter tariffs
- **LangChain adapter** - wrap any `Prompt` in `LangChainPromptAdapter` to work with `ChatPromptTemplate`
- **Zero dependencies** - SQLite only; LLM integrations are optional extras

## Quick Start

```python
from prompthub import Storage, PromptTag
from prompthub.core.tokenizers.openai_tag import OpenAIModelTag

store = Storage("prompts.db")

# Create prompt with initial version
prompt = store.create_prompt(
    "assistant",
    messages=[("system", "You are concise."), ("user", "Hi!")],
    tags=[PromptTag("production")],
    model_tags=[OpenAIModelTag("gpt-4o")],
)

# Add a new version
prompt.add_version([("system", "You are very concise."), ("user", "Hi!")])

# Diff two versions
diff = prompt.compare_versions_structured(1, 2)

# Soft rollback to version 1 (creates version 3)
prompt.rollback(target_seq=1)

# Fetch latest content as raw messages
messages = store.fetch_prompt("assistant")

# Fetch and work with LangChain
from prompthub.adapters import LangChainPromptAdapter
lc = LangChainPromptAdapter(store.get_prompt("assistant"))
template = lc.get_version_content(2)   # -> ChatPromptTemplate
```

## Project Structure

```
prompthub/
├── __init__.py              # Public API: Storage, Prompt, PromptGroup, PromptTag, ModelTag
├── adapters/                # High-level adapters (user-facing)
│   └── langchain.py         # LangChainPromptAdapter
├── facade/
│   ├── storage.py           # Storage - main entry point
│   ├── prompt.py            # Prompt - versions, tags, diff, rollback
│   └── prompt_group.py      # PromptGroup - bulk queries
├── core/
│   ├── domain/              # Domain models: operations, diff, tags, tariffs
│   ├── adapters/            # LLM serializers: LangChainAdapter + registry
│   └── tokenizers/          # Token counting: OpenAI, Anthropic, HuggingFace
├── infrastructure/
│   ├── pricing_gateway.py   # Fetch tariffs from OpenRouter API
│   └── tariff_manager.py    # Write tariffs to DB
├── repository/              # SQL layer: PromptRepo, query DSL, schema
└── search/
    └── filters.py           # Boolean filter DSL: FieldEquals, TagFilter, ...
```

## License

MIT
