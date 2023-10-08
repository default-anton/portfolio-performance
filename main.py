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


def set_etf_name_from_description(df, split_on):
    mask = df.Description.str.contains(split_on)
    df.loc[mask, "ETF Name"] = df.loc[mask, "Description"].str.split(split_on).str[0]


for split_on in [" WE ACTED AS AGENT", " CASH DIV ON", " DIST ON"]:
    set_etf_name_from_description(df, split_on)


def fix_etf_symbols(df):
    trades_mask = df["Activity Type"] == "Trades"
    valid_symbols_mask = ~df["Symbol"].fillna("").str.contains(r"\d")
    etfs_df = (
        df.loc[(trades_mask & valid_symbols_mask), ["Symbol", "ETF Name"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    df = pd.merge(df, etfs_df, on="ETF Name", how="left", suffixes=(None, "_valid"))
    df["Symbol"] = df["Symbol_valid"].fillna(df["Symbol"])
    df.drop(columns=["Symbol_valid"], inplace=True)

    return df


df = fix_etf_symbols(df)

# TODO: Allow filtering by account #
# TODO: Verify that dividends Net Amount is in CAD

start_date = df["Settlement Date"].min().date().isoformat()
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
df.drop(columns=["date"], inplace=True)

usd_mask = df["Currency"] == "USD"
usd_deposits_and_withdrawals_mask = usd_mask & (
    df["Activity Type"].isin(["Deposits", "Withdrawals"])
)

df.loc[usd_mask, ["Price", "Gross Amount", "Commission"]] = df.loc[
    usd_mask, ["Price", "Gross Amount", "Commission"]
].multiply(df.loc[usd_mask, "FXUSDCAD"], axis="index")
df.loc[usd_deposits_and_withdrawals_mask, "Net Amount"] *= df.loc[
    usd_deposits_and_withdrawals_mask, "FXUSDCAD"
]

# TODO: simplify this
valid_symbols_filter = (~df["Symbol"].isna()) & (
    ~df["Symbol"].fillna().str.contains("\d")
)
stocks = df[valid_symbols_filter]["Symbol"].unique()
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
dividends_df = df[df["Activity Type"] == "Dividends"]

print("Total deposits: {:.2f} CAD".format(deposits_df["Net Amount"].sum()))
print("Total withdrawals: {:.2f} CAD".format(withdrawals_df["Net Amount"].sum()))
print(
    "Total fees and rebates: {:.2f} CAD".format(fees_and_rebates_df["Net Amount"].sum())
)
print("Total interest: {:.2f} CAD".format(interest_df["Net Amount"].sum()))
print("Total dividends: {:.2f} CAD".format(dividends_df["Net Amount"].sum()))

print(f"Total!: {df['Net Amount'].sum():.2f} CAD")


# Function to get the current price of a stock
def get_current_price(symbol):
    stock = yf.Ticker(symbol)
    return stock.info["regularMarketPrice"]


# Get the current value of each stock in the portfolio
current_values = []
for symbol in trades_df["Symbol"].unique():
    # Filter the DataFrame for each stock
    stock_df = trades_df[trades_df["Symbol"] == symbol]
    # Get the quantity of the stock
    quantity = stock_df["Quantity"].sum()
    if quantity == 0:
        continue

    stock = yf.Ticker(symbol)
    current_value = quantity * stock.info["previousClose"]

    if stock.info["currency"] == "USD":
        current_value *= rates_df["FXUSDCAD"].iloc[-1]

    current_values.append(current_value)

portfolio_value = sum(current_values)
dividends_received = dividends_df["Net Amount"].sum()
fees_paid = fees_and_rebates_df["Net Amount"].sum()
initial_investment = deposits_df["Net Amount"].sum()
