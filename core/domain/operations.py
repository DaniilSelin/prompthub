
class Operation:
    def apply(self, content: str) -> str:
        raise NotImplementedError

class InsertOperation(Operation):
    def __init__(self, pos: int, text: str):
        self.pos = pos
        self.text = text

    def apply(self, content: str) -> str:
        if self.pos < 0:
            p = max(0, len(content) + self.pos)
        else:
            p = min(max(0, self.pos), len(content))
        return content[:p] + self.text + content[p:]

    def __repr__(self) -> str:
        return f"Insert(pos={self.pos}, text={self.text!r})"

class DeleteOperation(Operation):
    def __init__(self, start: int, end: int):
        self.start = start
        self.end = end

    def apply(self, content: str) -> str:
        s = max(0, min(self.start, len(content)))
        e = max(0, min(self.end, len(content)))
        if e <= s:
            return content
        return content[:s] + content[e:]

    def __repr__(self) -> str:
        return f"Delete(start={self.start}, end={self.end})"

class ReplaceOperation(Operation):
    def __init__(self, start: int, end: int, text: str):
        self.start = start
        self.end = end
        self.text = text

    def apply(self, content: str) -> str:
        s = max(0, min(self.start, len(content)))
        e = max(0, min(self.end, len(content)))
        if e < s:
            s, e = e, s
        return content[:s] + self.text + content[e:]

    def __repr__(self) -> str:
        return f"Replace(start={self.start}, end={self.end}, text={self.text!r})"
