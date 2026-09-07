"""Market-data ingestion worker."""


class MarketDataWorker:
    def __init__(self) -> None:
        self.running = False

    async def start(self) -> None:
        self.running = True

    async def stop(self) -> None:
        self.running = False
