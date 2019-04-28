import logging
import sys
import pandas as pd
from pandas import DataFrame
from pathlib import Path
import plotly.offline as pyo
import plotly.graph_objs as go
import dash
import dash_table
import dash_html_components as html
import dash_core_components as dcc

import arrow
from freqtrade.arguments import TimeRange
from freqtrade.data.history import parse_ticker_dataframe, load_pair_history
from freqtrade.persistence import Trade
from freqtrade.data.btanalysis import BT_DATA_COLUMNS, load_backtest_data
from freqtrade.exchange import Exchange
from freqtrade.optimize.backtesting import setup_configuration
from freqtrade.resolvers import StrategyResolver

app = dash.Dash()

DATA_DIR = Path("user_data/data/binance")
BACKTEST_RESULT_PATH = Path("user_data/backtest_data/backtest-result.json")

def get_ticker_data(pair:str, ticker_interval:str) -> DataFrame:
    return load_pair_history(pair, 
                            ticker_interval=ticker_interval,
                            datadir= DATA_DIR,
                            timerange=TimeRange(starttype ='date', startts=int(arrow.utcnow().shift(days=-60).float_timestamp)))

def load_trades(file:str) -> DataFrame:
    trades = pd.DataFrame([], columns=BT_DATA_COLUMNS)
    if file.exists():
        trades = load_backtest_data(file)
        trades['profitperc'] = round(trades['profitperc'] * 100,4)

    return trades

def get_price_chart(pair:str, ticker_interval:str):
    df = get_ticker_data(pair,ticker_interval)

    return go.Candlestick(x= df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'] )

def get_trades_chart(pair:str):
    trades = load_trades(BACKTEST_RESULT_PATH)

    trades = trades[trades['pair'] == pair]
    
    trade_buys = go.Scattergl(
        x=trades["open_time"],
        y=trades["open_rate"],
        mode='markers',
        name='trade_buy',
        marker=dict(
            symbol='square-open',
            size=11,
            line=dict(width=2),
            color='green'
        )
    )
    trade_sells = go.Scattergl(
        x=trades["close_time"],
        y=trades["close_rate"],
        mode='markers',
        name='trade_sell',
        marker=dict(
            symbol='square-open',
            size=11,
            line=dict(width=2),
            color='red'
        )
    )
    return [trade_buys, trade_sells]


def get_graph(pair:str, ticker_interval:str):
    price = get_price_chart(pair, ticker_interval)
    trades = get_trades_chart(pair)
    get_trades_chart(pair)

    layout = go.Layout(title=f"Results for {pair}({ticker_interval})")
    data = [price] + trades
    return go.Figure(data=data, layout=layout)


def setup_app_layout():
    fig = get_graph("BTC/USDT", "15m")
    app.layout = html.Div([
        html.H1("Freqtrade Dashboard", style={'textAlign': 'center', 'color': 'green'}),
        # dash_table.DataTable(
        #             id='table',
        #             columns=[{"name": i, "id": i} for i in df.columns],
        #             data=df.to_dict('records')
        #             )
        dcc.Graph(id='price_chart', figure=fig)

    ])

def main():
    setup_app_layout()
    app.run_server(debug=True)

if __name__ == "__main__":
    main()