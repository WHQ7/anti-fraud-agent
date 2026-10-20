class AgentError(Exception):
    """Only safe, deliberately authored messages should be exposed to the UI."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)
