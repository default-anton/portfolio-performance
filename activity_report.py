import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import cast

import pandas as pd

from bank_of_canada import get_cadx_rates
from ticker import Ticker


@dataclass
class ActivityReport:
    all: pd.DataFrame
    deposits: pd.DataFrame
    withdrawals: pd.DataFrame
    fees_and_rebates: pd.DataFrame
    interest: pd.DataFrame
    trades: pd.DataFrame
    dividends: pd.DataFrame

    @classmethod
    def load(cls, id: str) -> "ActivityReport":
        df = pd.read_csv(cls._file_path(id))

        return ActivityReport(
            all=df,
            deposits=cast(pd.DataFrame, df[df["Activity Type"] == "Deposits"]),
            withdrawals=cast(pd.DataFrame, df[df["Activity Type"] == "Withdrawals"]),
            fees_and_rebates=cast(
                pd.DataFrame, df[df["Activity Type"] == "Fees and rebates"]
            ),
            interest=cast(pd.DataFrame, df[df["Activity Type"] == "Interest"]),
            trades=cast(pd.DataFrame, df[df["Activity Type"] == "Trades"]),
            dividends=cast(pd.DataFrame, df[df["Activity Type"] == "Dividends"]),
        )

    @staticmethod
    def _file_path(id: str) -> Path:
        return Path("data") / f"activity_report_{id}.xlsx"

    def save(self) -> None:
        file_path = self._file_path(self.id)
        if file_path.exists():
            return

        self.all.to_csv(file_path, index=False)

    def current_value(self, fx_usdcad: float) -> float:
        current_values = []
        for symbol in self.trades["Symbol"].unique():
            # Filter the DataFrame for each stock
            stock_df = self.trades[self.trades["Symbol"] == symbol]
            # Get the quantity of the stock
            quantity = stock_df["Quantity"].sum()
            if quantity == 0:
                continue

            ticker = Ticker.load(symbol)
            current_value = quantity * ticker.price

            if ticker.currency == "USD":
                current_value *= fx_usdcad

            current_values.append(current_value)

        return sum(current_values)

    def initial_investment(self) -> float:
        return self.deposits["Net Amount"].sum() + self.withdrawals["Net Amount"].sum()

    def roi(self, fx_usdcad: float) -> float:
        return self.current_value(fx_usdcad) / self.initial_investment() - 1

    def deposits_sum(self) -> float:
        return self.deposits["Net Amount"].sum()

    def withdrawals_sum(self) -> float:
        return self.withdrawals["Net Amount"].sum()

    def fees_and_rebates_sum(self) -> float:
        return self.fees_and_rebates["Net Amount"].sum()

    def interest_sum(self) -> float:
        return self.interest["Net Amount"].sum()

    def trades_sum(self) -> float:
        return self.trades["Net Amount"].sum()

    def dividends_sum(self) -> float:
        return self.dividends["Net Amount"].sum()

    @property
    def id(self) -> str:
        return hashlib.sha256(self.all.to_csv().encode()).hexdigest()


def load_activity_report(
    file: bytes, account_number: str | None = None
) -> ActivityReport:
    df = pd.read_excel(file)

    if account_number:
        print(f"Filtering by account number: {account_number}")
        df = df[df["Account #"] == int(account_number)]

    df["Settlement Date"] = pd.to_datetime(df["Settlement Date"])
    df["Transaction Date"] = pd.to_datetime(df["Transaction Date"])

    for split_on in [" WE ACTED AS AGENT", " CASH DIV ON", " DIST ON"]:
        _set_etf_name_from_description(cast(pd.DataFrame, df), split_on)

    df = _fix_etf_symbols(cast(pd.DataFrame, df))

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
        all=df,
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
