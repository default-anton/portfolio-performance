from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
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

    @staticmethod
    def load_history(start: date, end: date, symbol: str) -> pd.DataFrame:
        if start.isoweekday() > 5:
            start = start - timedelta(days=start.isoweekday() - 5)

        if end.isoweekday() > 5:
            end = end - timedelta(days=end.isoweekday() - 5)

        cache_key = Path("data") / f"{symbol}-history.csv"
        if cache_key.exists():
            history_df = pd.read_csv(cache_key)
            history_df["Date"] = pd.to_datetime(history_df["Date"])
            history_df.set_index("Date", inplace=True)
            history_df = history_df.tz_localize(None)
            need_to_update = False

            if history_df.index.max() < pd.to_datetime(end):
                need_to_update = True
                delta_df = yf.Ticker(symbol).history(
                    interval="1d",
                    start=(history_df.index.max() + pd.Timedelta(days=1))
                    .to_pydatetime()
                    .date(),
                    end=end,
                )
                delta_df = delta_df.tz_localize(None)
                history_df = pd.concat([history_df, delta_df])

            if history_df.index.min() > pd.to_datetime(start):
                need_to_update = True
                delta_df = yf.Ticker(symbol).history(
                    interval="1d",
                    start=start,
                    end=(history_df.index.min() - pd.Timedelta(days=1))
                    .to_pydatetime()
                    .date(),
                )
                delta_df = delta_df.tz_localize(None)
                history_df = pd.concat([delta_df, history_df])

            history_df = history_df.sort_index()
            # Take the last value of each day
            history_df = history_df.groupby(history_df.index).last()

            if need_to_update:
                history_df.to_csv(cache_key, index=True, index_label="Date")

            return history_df

        history_df = yf.Ticker(symbol).history(
            interval="1d",
            start=start,
            end=end,
        )
        history_df = history_df.tz_localize(None)
        # Take the last value of each day
        history_df = history_df.groupby(history_df.index).last()
        history_df.to_csv(cache_key)

        return history_df

    @classmethod
    def load_from_cache(cls, cache_key: Path) -> "Ticker":
        with cache_key.open("r") as f:
            symbol, price, currency = f.read().split(",")
            return Ticker(symbol, float(price), currency)

    def save_to_cache(self, cache_key: Path) -> None:
        with cache_key.open("w") as f:
            f.write(f"{self.symbol},{self.price},{self.currency}")
