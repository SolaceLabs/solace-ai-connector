"""Trace message for debugging purposes."""


class TraceMessage:
    def __init__(self, message, location, type="Trace"):
        self.message = message
        self.location = location
        self.type = type

    def __str__(self):
        return f"{self.type} at {self.location}\n{self.message}\n"
