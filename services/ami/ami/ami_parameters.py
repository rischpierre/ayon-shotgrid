from typing import Any


class BoolParameter:
    """Boolean parameter for AMI forms."""

    def __init__(self, name: str, default: bool = False) -> None:
        self.name: str = name
        self.default: bool = bool(default)
        self._value: bool = bool(default)

    def set(self, value: Any) -> None:
        """Set the parameter value from a raw input (string or any truthy type)."""
        if isinstance(value, str):
            self._value = value.lower() in ("1", "true", "yes", "on")
        else:
            self._value = bool(value)

    def value(self) -> bool:
        """Return the current boolean value."""
        return self._value


class StringParameter:
    """String parameter for AMI forms."""

    def __init__(self, name: str, default: str = "") -> None:
        self.name: str = name
        self.default: str = default
        self._value: str = default

    def set(self, value: Any) -> None:
        """Set the parameter value from a raw input, coercing to string."""
        self._value = "" if value is None else str(value)

    def value(self) -> str:
        """Return the current string value."""
        return self._value
