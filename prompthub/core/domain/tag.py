class PromptTag:
    def __init__(self, value: str):
        self.value = value

    def __repr__(self) -> str:
        return f"PromptTag({self.value!r})"
