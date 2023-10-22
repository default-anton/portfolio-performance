from collections import defaultdict

from svc.activity_report import ActivityReport


class ActivityReportView:
    def __init__(self, activity_report: ActivityReport):
        self.activity_report = activity_report

    def portfolio_growth(
        self, accounts: list[int] | None = None
    ) -> list[dict[str, str | float]]:
        df = self.activity_report.portfolio_growth(accounts)
        df = df.groupby("Date").agg({"Gross Amount": "sum"}).reset_index()
        df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
        df.rename(columns={"Date": "x", "Gross Amount": "y"}, inplace=True)

        return df.to_dict(orient="records")

    def etfs_growth(self, accounts: list[int] | None = None) -> list[dict]:
        df = self.activity_report.portfolio_growth(accounts)
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
