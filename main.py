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

rates_df = get_cadx_rates(start_date, end_date)
# Merge rates with transactions
df = pd.merge_asof(
    df.sort_values("Settlement Date"),
    rates_df,
    left_on="Settlement Date",
    right_on="date",
    direction="backward",
)
df["PriceInAccountCurrency"] = df["Price"]
df.loc[df["Currency"] == "USD", "PriceInCAD"] = (
    df["Price"] * df["FXUSDCAD"]
)
del df["Price"]

stocks = [s for s in df["Symbol"].dropna().unique() if not any(c.isdigit() for c in s)]
# Securities listed on TSX often have .TO suffix
tsx_stocks = [s for s in stocks if s.endswith(".TO")]
# Find TSX listed stocks without .TO suffix
stocks = list(set(stocks) - set([s.removesuffix(".TO") for s in tsx_stocks]))
# Replace stocks without .TO suffix with stocks with .TO suffix
df["Symbol"] = df["Symbol"].replace(
    [s.removesuffix(".TO") for s in tsx_stocks], tsx_stocks
)
tsx_filter = df["Symbol"].map(lambda x: str(x) + ".TO").isin(tsx_stocks)
df.loc[tsx_filter, "Symbol"] = df[tsx_filter]["Symbol"].map(lambda x: x + ".TO")

deposits_df = df[df["Activity Type"] == "Deposits"]
withdrawals_df = df[df["Activity Type"] == "Withdrawals"]
fees_and_rebates_df = df[df["Activity Type"] == "Fees and Rebates"]
interest_df = df[df["Activity Type"] == "Interest"]
trades_df = df[df["Activity Type"] == "Trades"]
dividents_df = df[df["Activity Type"] == "Dividends"]

import pdb

pdb.set_trace()


# TODO: contributions and withdrawals
# TODO: current portfolio value
# TODO: dividends and distributions
# TODO: fees and expenses
# TODO: interest
