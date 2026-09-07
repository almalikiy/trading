"""Execution worker."""


class ExecutionWorker:
    def __init__(self) -> None:
        self.running = False

    async def start(self) -> None:
        self.running = True

    async def stop(self) -> None:
        self.running = False
