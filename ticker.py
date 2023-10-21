from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yfinance as yf


@dataclass
class Ticker:
    symbol: str
    price: float
    currency: str

    @classmethod
    def load(cls, symbol: str, day: date | None = None) -> "Ticker":
        if day is None:
            day = date.today()

        cache_key = Path("data") / f"ticker-{day.strftime('%Y-%m-%d')}-{symbol}.csv"
        if cache_key.exists():
            return cls.load_from_cache(cache_key)

        info = yf.Ticker(symbol).info
        ticker = Ticker(
            symbol=symbol,
            currency=info["currency"],
            price=info["previousClose"],
        )
        ticker.save_to_cache(cache_key)

        return ticker

    @classmethod
    def load_from_cache(cls, cache_key: Path) -> "Ticker":
        with cache_key.open("r") as f:
            symbol, price, currency = f.read().split(",")
            return Ticker(symbol, float(price), currency)

    def save_to_cache(self, cache_key: Path) -> None:
        with cache_key.open("w") as f:
            f.write(f"{self.symbol},{self.price},{self.currency}")
