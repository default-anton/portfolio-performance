import datetime
import io
import sys

import pandas as pd
import requests

# read path to the data file from arguments


# Download Bank of Canada exchange rates
def get_rates():
    start_date = datetime.date.today().replace(day=1, month=1).isoformat()
    end_date = datetime.date.today().isoformat()
    path = f"https://www.bankofcanada.ca/valet/observations/FXUSDCAD/csv?start_date={start_date}&end_date={end_date}"

    csv = requests.get(path).content.decode("utf-8")
    csv = csv[csv.find('"date"'):]
    return pd.read_csv(io.StringIO(csv))


rates_df = get_rates()
rates_df['date'] = pd.to_datetime(rates_df['date'], format='%Y-%m-%d')

if len(sys.argv) < 2:
    print("Please provide the path to the data file")
    exit(1)

df = pd.read_excel(sys.argv[1])
df.head()
# Index(['Transaction Date', 'Settlement Date', 'Action', 'Symbol',
# 'Description', 'Quantity', 'Price', 'Gross Amount', 'Commission',
# 'Net Amount', 'Currency', 'Account #', 'Activity Type', 'Account Type'],
# dtype='object')

df['Settlement Date'] = pd.to_datetime(df['Settlement Date'], format='%Y-%m-%d')

trades_df = df[df["Activity Type"] == "Trades"]
dividents_df = df[df["Activity Type"] == "Dividends"]


# Merge on closest earlier or same date
trades_df = pd.merge_asof(trades_df.sort_values('Settlement Date'), rates_df, left_on='Settlement Date', right_on='date', direction='backward')
trades_df.loc[trades_df['Currency'] == 'USD', 'Price'] *= trades_df['FXUSDCAD']

dividents_df = pd.merge_asof(dividents_df.sort_values('Settlement Date'), rates_df, left_on='Settlement Date', right_on='date', direction='backward')
dividents_df.loc[dividents_df['Currency'] == 'USD', 'Price'] *= dividents_df['FXUSDCAD']


(trades_df["Price"] * trades_df["Quantity"]).sum()
