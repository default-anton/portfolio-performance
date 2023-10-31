import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import cast

import pandas as pd

from svc.bank_of_canada import get_cadx_rates
from svc.ticker import Ticker


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
        df["Settlement Date"] = pd.to_datetime(df["Settlement Date"])
        df["Transaction Date"] = pd.to_datetime(df["Transaction Date"])

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

    @property
    def start_date(self) -> date:
        return self.all["Settlement Date"].min().date()

    def portfolio(self, drop_zero_shares: bool = False) -> pd.DataFrame:
        ar = self
        df = (
            ar.trades.groupby(["Account #", "Symbol"])
            .agg({"Quantity": "sum"})
            .reset_index()
        )
        if drop_zero_shares:
            df.drop(df[df["Quantity"] == 0].index, inplace=True)

        df.rename(columns={"Account #": "Account", "Quantity": "Shares"}, inplace=True)

        return df

    def current_value(self, boc_usdcad: float) -> float:
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
                current_value *= boc_usdcad

            current_values.append(current_value)

        return sum(current_values)

    def initial_investment(self) -> float:
        return self.deposits["Net Amount"].sum() + self.withdrawals["Net Amount"].sum()

    def roi(self, boc_usdcad: float) -> float:
        return self.current_value(boc_usdcad) / self.initial_investment() - 1

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

    def net_amount_cumsum(self) -> list[dict]:
        df = self.all.groupby("Settlement Date").agg({"Net Amount": "sum"}).cumsum()
        df.reset_index(inplace=True)
        df["Net Amount"] = df["Net Amount"].round(2)
        df["Settlement Date"] = df["Settlement Date"].dt.strftime("%Y-%m-%d")
        df.rename(columns={"Settlement Date": "x", "Net Amount": "y"}, inplace=True)
        return df.to_dict(orient="records")

    def net_amount_cumsum_labels(self) -> list[str]:
        return [e["x"] for e in self.net_amount_cumsum()]

    def portfolio_growth(self, accounts: list[int] | None = None) -> pd.DataFrame:
        if accounts is None or len(accounts) == 0:
            trades = self.trades
        else:
            trades = self.trades[self.trades["Account #"].isin(accounts)]

        symbols = trades["Symbol"].unique()
        # index: Date; columns: Open, High, Low, Close, Volume
        price_history_by_ticker: dict[str, pd.DataFrame] = {
            symbol: Ticker.load_history(
                symbol=symbol,
                start=trades.loc[trades["Symbol"] == symbol, "Settlement Date"]
                .min()
                .date(),
                end=date.today(),
            )
            for symbol in symbols
        }

        df = pd.DataFrame()
        for ticker, price_history in price_history_by_ticker.items():
            etf_df = trades[trades["Symbol"] == ticker]
            etf_df = (
                etf_df.groupby("Settlement Date").agg({"Quantity": "sum"}).reset_index()
            )
            etf_df.loc[:, "Shares"] = etf_df["Quantity"].cumsum()
            etf_df.rename(columns={"Settlement Date": "Date"}, inplace=True)
            etf_df.set_index("Date", inplace=True)
            etf_df = price_history.merge(
                etf_df[["Shares"]],
                how="left",
                left_index=True,
                right_index=True,
            )
            currency = trades[trades["Symbol"] == ticker]["Currency"].iloc[0]
            etf_df = etf_df.assign(Symbol=ticker, Currency=currency)
            etf_df["Shares"].ffill(inplace=True)
            etf_df["Shares"].fillna(0, inplace=True)
            etf_df.reset_index(inplace=True, names=["Date"])
            etf_df.set_index(["Date", "Symbol"], inplace=True)
            df = pd.concat([df, etf_df])

        df.sort_index(inplace=True)
        df.reset_index(inplace=True)

        rates_df = get_cadx_rates(trades["Settlement Date"].min().date(), date.today())
        df = pd.merge_asof(
            df,
            rates_df,
            left_on="Date",
            right_on="date",
            direction="backward",
        )

        usd_mask = df["Currency"] == "USD"
        df.loc[usd_mask, ["Open", "High", "Low", "Close"]] = df.loc[
            usd_mask, ["Open", "High", "Low", "Close"]
        ].multiply(df.loc[usd_mask, "FXUSDCAD"], axis="index")
        df.drop(columns=["date", "FXUSDCAD"], inplace=True)
        df.loc[:, "Gross Amount"] = df["Shares"] * df["Close"]

        return df

    @property
    def id(self) -> str:
        return hashlib.sha256(self.all.to_csv().encode()).hexdigest()


def load_activity_report(
    file: bytes, account_number: str | None = None
) -> ActivityReport:
    df = pd.read_excel(file)

    if account_number:
        df = df[df["Account #"] == int(account_number)]

    df["Settlement Date"] = pd.to_datetime(df["Settlement Date"])
    df["Transaction Date"] = pd.to_datetime(df["Transaction Date"])

    for split_on in [" WE ACTED AS AGENT", " CASH DIV ON", " DIST ON"]:
        _set_etf_name_from_description(cast(pd.DataFrame, df), split_on)

    df = _fix_etf_symbols(cast(pd.DataFrame, df))

    start_date = df["Settlement Date"].min().date()
    end_date = date.today()

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
