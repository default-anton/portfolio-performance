from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import cast

import pandas as pd

from svc.activity_report import ActivityReport


@dataclass
class Account:
    id: int
    account_type: str

    def __str__(self) -> str:
        return f"{self.id} ({self.account_type})"


class ActivityReportView:
    def __init__(
        self,
        activity_report: ActivityReport,
        selected_accounts: list[int] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ):
        self.activity_report = activity_report
        self.selected_accounts = selected_accounts
        self.start_date = start_date
        self.end_date = end_date

    @property
    def all_accounts(self) -> list[Account]:
        accounts = (
            self.activity_report.all[["Account #", "Account Type"]]
            .drop_duplicates()
            .to_dict(orient="records")
        )
        return [
            Account(id=cast(int, a["Account #"]), account_type=a["Account Type"])
            for a in accounts
        ]

    def portfolio_growth(self) -> list[dict[str, str | float]]:
        df = self.activity_report.portfolio_growth(self.selected_accounts)
        df = df.groupby("Date").agg({"Gross Amount": "sum"}).reset_index()
        df.sort_values("Date", inplace=True)

        if self.start_date is not None:
            df = df[df["Date"] >= pd.to_datetime(self.start_date)]

        if self.end_date is not None:
            df = df[df["Date"] <= pd.to_datetime(self.end_date)]

        df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
        df.rename(columns={"Date": "x", "Gross Amount": "y"}, inplace=True)

        return df.to_dict(orient="records")

    def etfs_growth(self) -> list[dict]:
        df = self.activity_report.portfolio_growth(self.selected_accounts)
        df.sort_values("Date", inplace=True)

        if self.start_date is not None:
            df = df[df["Date"] >= pd.to_datetime(self.start_date)]

        if self.end_date is not None:
            df = df[df["Date"] <= pd.to_datetime(self.end_date)]

        df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
        df.rename(columns={"Date": "x", "Gross Amount": "y"}, inplace=True)
        records = df.to_dict(orient="records")

        result: dict[str, dict] = defaultdict(
            lambda: {"data": [], "fill": False, "lineTension": 0.4}
        )
        for record in records:
            d = result[record["Symbol"]]
            d["label"] = record["Symbol"]
            d["data"].append({"x": record["x"], "y": record["y"]})

        return list(result.values())
