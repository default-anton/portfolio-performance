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

df.loc[df["Currency"] == "USD", "Price"] *= df["FXUSDCAD"]
df.loc[df["Currency"] == "USD", "Net Amount"] *= df["FXUSDCAD"]

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
fees_and_rebates_df = df[df["Activity Type"] == "Fees and rebates"]
interest_df = df[df["Activity Type"] == "Interest"]
trades_df = df[df["Activity Type"] == "Trades"]
dividents_df = df[df["Activity Type"] == "Dividends"]


print("Total deposits: {:.2f} CAD".format(deposits_df["Net Amount"].sum()))
print("Total withdrawals: {:.2f} CAD".format(withdrawals_df["Net Amount"].sum()))
print("Total fees and rebates: {:.2f} CAD".format(fees_and_rebates_df["Net Amount"].sum()))
print("Total interest: {:.2f} CAD".format(interest_df["Net Amount"].sum()))
print("Total dividends: {:.2f} CAD".format(dividents_df["Net Amount"].sum()))

total = (
    deposits_df["Net Amount"].sum()
    + withdrawals_df["Net Amount"].sum()
    + fees_and_rebates_df["Net Amount"].sum()
    + interest_df["Net Amount"].sum()
    + dividents_df["Net Amount"].sum()
)
# Format to 2 decimal places
print("Total: {:.2f} CAD".format(total))


# TODO: current portfolio value
