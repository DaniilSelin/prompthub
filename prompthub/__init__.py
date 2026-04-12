"""PromptHub — prompt version control system built on SQLite.

Quickstart
----------
    from prompthub import Storage

    store = Storage("prompts.db")
    prompt = store.create_prompt("my-prompt")
    prompt.add_version([("system", "You are helpful."), ("user", "Hello")])

Optional extras
---------------
Install only what you need::

    pip install prompthub                          # core only (stdlib)
    pip install prompthub[all]                     # everything
    pip install prompthub[langchain]               # + LangChain adapter
    pip install prompthub[openai]                  # + OpenAI tokenizer
    pip install prompthub[anthropic]               # + Anthropic tokenizer
    pip install prompthub[huggingface]             # + HuggingFace tokenizer
    pip install prompthub[langchain,openai]        # any combination
"""

from prompthub.facade.prompt import Prompt, PromptVersion
from prompthub.facade.prompt_group import PromptGroup
from prompthub.facade.storage import Storage
from prompthub.core.domain.tag import PromptTag
from prompthub.core.tokenizers.base import ModelTag

__all__ = [
    "Storage",
    "Prompt",
    "PromptVersion",
    "PromptGroup",
    "PromptTag",
    "ModelTag",
]

__version__ = "0.1.0"
