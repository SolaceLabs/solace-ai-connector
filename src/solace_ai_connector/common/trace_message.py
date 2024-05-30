"""Trace message for debugging purposes."""


class TraceMessage:
    def __init__(self, message, location, trace_type="Trace"):
        self.message = message
        self.location = location
        self.trace_type = trace_type

    def __str__(self):
        return f"{self.trace_type} at {self.location}\n{self.message}\n"
