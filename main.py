# https://medium.datadriveninvestor.com/the-supertrend-implementing-screening-backtesting-in-python-70e8f88f383d
# https://ark-funds.com/wp-content/uploads/funds-etf-csv/ARK_INNOVATION_ETF_ARKK_HOLDINGS.csv
#
import pandas as pd
import numpy as np
import yfinance as yf
import ssl
import time
from datetime import date
import csv
from scipy.stats import linregress
import numpy as np
import requests
import itertools


def momentum(closes):
    if closes.empty:
        return 0
    returns = np.log(closes)
    x = np.arange(len(returns))
    slope, _, rvalue, _, _ = linregress(x, returns)
    return ((1 + slope) ** 252) * (rvalue ** 2)  # annualize slope and multiply by R^2


def Supertrend(df, atr_period, multiplier):
    high = df['High']
    low = df['Low']
    close = df['Close']

    # calculate ATR
    price_diffs = [high - low,
                   high - close.shift(),
                   close.shift() - low]
    true_range = pd.concat(price_diffs, axis=1)
    true_range = true_range.abs().max(axis=1)
    # default ATR calculation in supertrend indicator
    atr = true_range.ewm(alpha=1 / atr_period, min_periods=atr_period).mean()
    # df['atr'] = df['tr'].rolling(atr_period).mean()

    # HL2 is simply the average of high and low prices
    hl2 = (high + low) / 2
    # upperband and lowerband calculation
    # notice that final bands are set to be equal to the respective bands
    final_upperband = upperband = hl2 + (multiplier * atr)
    final_lowerband = lowerband = hl2 - (multiplier * atr)

    # initialize Supertrend column to True
    supertrend = [True] * len(df)

    for i in range(1, len(df.index)):
        curr, prev = i, i - 1

        # if current close price crosses above upperband
        if close[curr] > final_upperband[prev]:
            supertrend[curr] = True
        # if current close price crosses below lowerband
        elif close[curr] < final_lowerband[prev]:
            supertrend[curr] = False
        # else, the trend continues
        else:
            supertrend[curr] = supertrend[prev]

            # adjustment to the final bands
            if supertrend[curr] == True and final_lowerband[curr] < final_lowerband[prev]:
                final_lowerband[curr] = final_lowerband[prev]
            if supertrend[curr] == False and final_upperband[curr] > final_upperband[prev]:
                final_upperband[curr] = final_upperband[prev]

        # to remove bands according to the trend direction
        if supertrend[curr] == True:
            final_upperband[curr] = np.nan
        else:
            final_lowerband[curr] = np.nan

    return pd.DataFrame({
        'Supertrend': supertrend,
        'Final Lowerband': final_lowerband,
        'Final Upperband': final_upperband
    }, index=df.index)


def find(name, stock_list):
    for symbol in stock_list:
        time.sleep(2)
        symbol = symbol.replace(".", "-")
        symbol = symbol.replace(" ", "")
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1Y", interval="1d")
        cnt = 0
        while len(df) == 0 and cnt < 3:
            cnt = cnt + 1
            time.sleep(2)
            df = ticker.history(period="1Y", interval="1d")
        supertrend_stocks[symbol] = Supertrend(df, atr_period, atr_multiplier)
        stock_history[symbol] = df
        with open('StockPrice-' + date.today().strftime("%d-%m-%Y") + ".csv", 'a+') as outfile:
            csv_writer = csv.writer(outfile)
            row = [symbol, stock_history[symbol].index[5], stock_history[symbol]['Close'][5]]
            csv_writer.writerow(row)


atr_period = 10
atr_multiplier = 3.0
supertrend_stocks = dict()
stock_history = dict()
stock_list = dict()
portflio = dict()
sotm = dict()
ssl._create_default_https_context = ssl._create_unverified_context
payload = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
stock_list = payload[0]['Symbol'].values.tolist()[0:5]
find('S&P500', stock_list)
for i in range(89, 253):
    for key in supertrend_stocks:
        supertrend = supertrend_stocks[key]
        sotm[key] = momentum(stock_history[key]['Close'][i - 89:i])
    sorted_sotm = dict(sorted(sotm.items(), key=lambda x: x[1], reverse=True))
    counter = 0
    top_20 = set()
    top_40 = set()
    for key in sorted_sotm:
        if counter < 20:
            top_20.add(key)
        if counter < 40:
            top_40.add(key)
        else:
            break
        counter = counter+1

    sold = []
    for key in portflio:
        if not supertrend['Supertrend'][i] or key not in top_40:
            with open('NewBackTest-' + date.today().strftime("%d-%m-%Y") + ".csv", 'a+') as outfile:
                csv_writer = csv.writer(outfile)
                pl = (stock_history[key]['Close'][i] - portflio[key][0]) * 100 / portflio[key][0]
                hold_time = i - portflio[key][1]
                row = [key, portflio[key][0], portflio[key][1], stock_history[key]['Close'][i], i, pl, hold_time]
                csv_writer.writerow(row)
            sold.append(key)
    for key in sold:
        portflio.pop(key)

    for key in top_20:
        if len(supertrend) > i and not supertrend['Supertrend'][i - 1] and supertrend['Supertrend'][i] and key not in portflio:
            portflio[key] = [stock_history[key]['Close'][i], i]
