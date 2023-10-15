from dataclasses import dataclass
from datetime import date
from typing import cast

import pandas as pd
import yfinance as yf

from bank_of_canada import get_cadx_rates


@dataclass
class ActivityReport:
    deposits: pd.DataFrame
    withdrawals: pd.DataFrame
    fees_and_rebates: pd.DataFrame
    interest: pd.DataFrame
    trades: pd.DataFrame
    dividends: pd.DataFrame


def load_activity_report(
    path: str, account_number: str | None = None
) -> ActivityReport:
    df = pd.read_excel(path)

    if account_number:
        print(f"Filtering by account number: {account_number}")
        df = df[df["Account #"] == int(account_number)]

    df["Settlement Date"] = pd.to_datetime(df["Settlement Date"])
    df["Transaction Date"] = pd.to_datetime(df["Transaction Date"])

    for split_on in [" WE ACTED AS AGENT", " CASH DIV ON", " DIST ON"]:
        _set_etf_name_from_description(df, split_on)

    df = _fix_etf_symbols(df)

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
    df.loc[usd_mask, ["Price", "Gross Amount", "Commission"]] = df.loc[
        usd_mask, ["Price", "Gross Amount", "Commission"]
    ].multiply(df.loc[usd_mask, "FXUSDCAD"], axis="index")

    deposits_and_withdrawals_mask = df["Activity Type"].isin(
        ["Deposits", "Withdrawals"]
    )
    dividends_mask = df["Activity Type"] == "Dividends"
    interest_mask = df["Activity Type"] == "Interest"
    mask = usd_mask & (deposits_and_withdrawals_mask | dividends_mask | interest_mask)
    df.loc[mask, "Net Amount"] = df.loc[mask, "Net Amount"].multiply(
        df.loc[mask, "FXUSDCAD"], axis="index"
    )

    return ActivityReport(
        deposits=cast(pd.DataFrame, df[df["Activity Type"] == "Deposits"]),
        withdrawals=cast(pd.DataFrame, df[df["Activity Type"] == "Withdrawals"]),
        fees_and_rebates=cast(
            pd.DataFrame, df[df["Activity Type"] == "Fees and rebates"]
        ),
        interest=cast(pd.DataFrame, df[df["Activity Type"] == "Interest"]),
        trades=cast(pd.DataFrame, df[df["Activity Type"] == "Trades"]),
        dividends=cast(pd.DataFrame, df[df["Activity Type"] == "Dividends"]),
    )


def _set_etf_name_from_description(df: pd.DataFrame, split_on: str) -> None:
    mask = df.Description.str.contains(split_on)
    df.loc[mask, "ETF Name"] = df.loc[mask, "Description"].str.split(split_on).str[0]


def _fix_etf_symbols(df: pd.DataFrame) -> pd.DataFrame:
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


# Function to get the current price of a stock
def get_current_price(symbol: str) -> float:
    stock = yf.Ticker(symbol)
    return stock.info["regularMarketPrice"]


# TODO: Return df with current stock prices
def todo_portfolio_value(trades_df: pd.DataFrame, rates_df: pd.DataFrame) -> float:
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

    return sum(current_values)
