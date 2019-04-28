import logging
import sys
from argparse import Namespace
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from plotly.offline import pyo
from plotly.graph_objs import go
from freqtrade.persistence import Trade
from freqtrade.data.btanalysis import BT_DATA_COLUMNS, load_backtest_data
from freqtrade.exchange import Exchange
from freqtrade.optimize.backtesting import setup_configuration

from freqtrade.resolvers import StrategyResolver


def load_trades(args: Namespace, pair: str, timerange: TimeRange) -> pd.DataFrame:
    trades: pd.DataFrame = pd.DataFrame()
    if args.db_url:
        persistence.init(_CONF)
        columns = ["pair", "profit", "open_time", "close_time",
                   "open_rate", "close_rate", "duration"]

        for x in Trade.query.all():
            print("date: {}".format(x.open_date))

        trades = pd.DataFrame([(t.pair, t.calc_profit(),
                                t.open_date.replace(tzinfo=timeZone),
                                t.close_date.replace(tzinfo=timeZone) if t.close_date else None,
                                t.open_rate, t.close_rate,
                                t.close_date.timestamp() - t.open_date.timestamp()
                                if t.close_date else None)
                               for t in Trade.query.filter(Trade.pair.is_(pair)).all()],
                              columns=columns)

    elif args.exportfilename:

        file = Path(args.exportfilename)
        if file.exists():
            load_backtest_data(file)

        else:
            trades = pd.DataFrame([], columns=BT_DATA_COLUMNS)

    return trades