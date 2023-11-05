import io
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

DB_PATH = Path("data") / "cadx.csv"


def get_cadx_rate(d: date) -> float:
    if d.isoweekday() > 5:
        d = d - timedelta(days=d.isoweekday() - 5)

    rates_df = get_cadx_rates(d, d)
    return rates_df["FXUSDCAD"].iloc[-1]


def get_cadx_rates(start_date: date, end_date: date):
    if start_date.isoweekday() > 5:
        start_date = start_date - timedelta(days=start_date.isoweekday() - 5)

    if end_date.isoweekday() > 5:
        end_date = end_date - timedelta(days=end_date.isoweekday() - 5)

    try:
        rates_df = pd.read_csv(DB_PATH, parse_dates=["date"], date_format="%Y-%m-%d")
        rates_df["date"] = pd.to_datetime(rates_df["date"], format="%Y-%m-%d")

        if rates_df["date"].min() > pd.to_datetime(start_date):
            rates_df = (
                fetch_cadx_rates(start_date, rates_df["date"].min().date()) + rates_df
            )

        if rates_df["date"].max() < pd.to_datetime(end_date):
            missing_rates_df = fetch_cadx_rates(rates_df["date"].max().date(), end_date)
            rates_df = (
                pd.concat((rates_df, missing_rates_df), ignore_index=True)
                .drop_duplicates()
                .sort_values("date")
            )

        rates_df.to_csv(DB_PATH, index=False)

        return rates_df
    except FileNotFoundError:
        rates_df = fetch_cadx_rates(start_date, end_date)
        rates_df.to_csv(DB_PATH, index=False)
        return rates_df


def fetch_cadx_rates(start_date: date, end_date: date):
    path = f"https://www.bankofcanada.ca/valet/observations/FXUSDCAD/csv?start_date={start_date}&end_date={end_date}"
    csv = requests.get(path).content.decode("utf-8")
    csv = csv[csv.find('"date"'):]

    rates_df = pd.read_csv(
        io.StringIO(csv), parse_dates=["date"], date_format="%Y-%m-%d"
    )
    rates_df["date"] = pd.to_datetime(rates_df["date"], format="%Y-%m-%d")

    return rates_df
