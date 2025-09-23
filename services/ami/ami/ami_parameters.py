from typing import Any


class BoolParameter:

    def __init__(self, name: str, default: bool = False) -> None:
        self.name: str = name
        self.default: bool = bool(default)
        self._value: bool = bool(default)

    def set(self, value: Any) -> None:
        self._value = bool(value)

    def value(self) -> bool:
        return self._value


class StringParameter:

    def __init__(self, name: str, default: str = "") -> None:
        self.name: str = name
        self.default: str = default
        self._value: str = default

    def set(self, value: Any) -> None:
        self._value = "" if value is None else str(value)

    def value(self) -> str:
        return self._value
