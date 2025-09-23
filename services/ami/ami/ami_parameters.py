class BoolParameter:
    def __init__(self, name, default=False):
        self.name = name
        self.default = bool(default)
        self._value = bool(default)

    def set(self, value_str):
        # Accept common truthy strings
        if isinstance(value_str, str):
            self._value = value_str.lower() in ("1", "true", "yes", "on")
        else:
            self._value = bool(value_str)

    def value(self):
        return self._value


class StringParameter:
    def __init__(self, name, default=""):
        self.name = name
        self.default = default
        self._value = default

    def set(self, value_str):
        self._value = "" if value_str is None else str(value_str)

    def value(self):
        return self._value
