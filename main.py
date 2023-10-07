import sys
from datetime import date

import pandas as pd

# https://pypi.org/project/yfinance/
import yfinance as yf

from bank_of_canada import get_cadx_rates

if len(sys.argv) < 2:
    print("Please provide the path to the data file")
    exit(1)


df = pd.read_excel(sys.argv[1])
df["Settlement Date"] = pd.to_datetime(df["Settlement Date"])
df["Transaction Date"] = pd.to_datetime(df["Transaction Date"])


start_date = df["Settlement Date"].min().isoformat()
end_date = date.today().isoformat()

stocks = [s for s in df["Symbol"].dropna().unique() if not any(c.isdigit() for c in s)]
tsx_stocks = [s for s in stocks if s.endswith(".TO")]
# Remove TSX stocks without .TO suffix
stocks = list(set(stocks) - set([s.removesuffix(".TO") for s in tsx_stocks]))
# Replace TSX stocks without .TO suffix with .TO suffix
df["Symbol"] = df["Symbol"].replace(
    [s.removesuffix(".TO") for s in tsx_stocks], tsx_stocks
)

tsx_filter = df["Symbol"].map(lambda x: str(x) + ".TO").isin(tsx_stocks)
df.loc[tsx_filter, "Symbol"] = df[tsx_filter]["Symbol"].map(lambda x: x + ".TO")

rates_df = get_cadx_rates(start_date, end_date)

trades_df = df[df["Activity Type"] == "Trades"]
dividents_df = df[df["Activity Type"] == "Dividends"]

# Merge on closest earlier or same date
trades_df = pd.merge_asof(
    trades_df.sort_values("Settlement Date"),
    rates_df,
    left_on="Settlement Date",
    right_on="date",
    direction="backward",
)
trades_df["PriceInAccountCurrency"] = trades_df["Price"]
trades_df.loc[trades_df["Currency"] == "USD", "PriceInCAD"] = (
    trades_df["Price"] * trades_df["FXUSDCAD"]
)
del trades_df["Price"]

dividents_df = pd.merge_asof(
    dividents_df.sort_values("Settlement Date"),
    rates_df,
    left_on="Settlement Date",
    right_on="date",
    direction="backward",
)
dividents_df["PriceInAccountCurrency"] = dividents_df["Price"]
dividents_df.loc[dividents_df["Currency"] == "USD", "PriceInCAD"] = (
    dividents_df["Price"] * dividents_df["FXUSDCAD"]
)
del dividents_df["Price"]


# TODO: contributions and withdrawals
# TODO: current portfolio value
# TODO: dividends and distributions
# TODO: fees and expenses
# TODO: interest
