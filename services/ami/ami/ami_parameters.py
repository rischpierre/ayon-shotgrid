


class BoolParameter:
    def __init__(self, name, default=False):
        self.name = name
        self.default = default

    def value(self):
        # todo how to impolement
        return ""


class StringParameter:
    def __init__(self, name, default=""):
        self.name = name
        self.default = default