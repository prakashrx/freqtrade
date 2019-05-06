# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
import logging
import talib.abstract as ta
import pandas as pd
import numpy as np
from pandas import DataFrame
import arrow
from pathlib import Path
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.arguments import TimeRange
from freqtrade.indicator_helpers import fishers_inverse
from freqtrade.strategy.interface import IStrategy
from freqtrade.state import RunMode
from freqtrade.strategy.util import resample_to_interval, resampled_merge
from freqtrade.data.history import parse_ticker_dataframe, load_pair_history
import freqtrade.indicators as indicators

logger = logging.getLogger("IchimokuStrategy")

class RenkoStrategy(IStrategy):

    cache = {}
    min_days = 30

    def get_extend_historical(self, pair: str, dataframe: DataFrame) -> DataFrame:

        if hasattr(self, 'dp'):
            if self.dp.runmode in (RunMode.LIVE, RunMode.DRY_RUN):
                min_date = dataframe['date'].min()
                if pair not in self.cache or self.cache[pair]["date"].max() < min_date:
                    logger.info(f"Downloading historical ohlc for pair: {pair})")
                    # hist = self.dp._exchange.get_history(pair=pair, ticker_interval=self.ticker_interval,
                    #                         since_ms=int(arrow.utcnow().shift(days=-60).float_timestamp) * 1000)
                    # self.cache[pair] = parse_ticker_dataframe(hist,self.ticker_interval)
                    self.cache[pair] = load_pair_history(pair, 
                                        ticker_interval=self.ticker_interval, 
                                        datadir= Path(f"user_data/data/history"),
                                        timerange=TimeRange(starttype ='date', startts=int(arrow.utcnow().shift(days=-60).float_timestamp)),
                                        refresh_pairs=True,
                                        exchange=self.dp._exchange)

                hist_df = self.cache[pair]
                min_date = dataframe['date'].min()
                return pd.concat([ hist_df[hist_df['date'] < min_date] , dataframe ])

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        
        dataframe = self.get_extend_historical(metadata['pair'], dataframe)
        if (dataframe['date'].max() - dataframe['date'].min()).days < self.min_days:
            return dataframe

        print(f"Calculating Renko for Pair: {metadata['pair']}")
        renko = self.calculate_renko(dataframe)
        print(f"Finished Calculating Renko for Pair: {metadata['pair']}")
        dataframe = pd.merge(dataframe, renko, on='date', how='left')
        dataframe.fillna(method='ffill', inplace=True)

        return dataframe

    def calculate_renko(self, df):
        df = df.dropna()
        df['atr'] = ta.ATR(df)
        df['atr'] = df['atr'].rolling(14).mean().round()

        renko = pd.DataFrame(columns=['date', 'renko_open', 'renko_close'])
        renko.loc[0] = [df.loc[0,'date'],df.loc[0,'close'],df.loc[0,'close']]

        for index,row in df.iloc[1:].iterrows():
            prev_close = renko.iloc[-1]['renko_close']
            prev_open  = renko.iloc[-1]['renko_open']
            atr = row['atr']
            direction = 1 if prev_close >= prev_open else -1
            if direction == 1:
                while prev_close + atr <= row['close']:
                    renko.loc[len(renko)] = [row['date'], prev_close, prev_close + atr]
                    prev_open = prev_close
                    prev_close = prev_close + atr
                while prev_open - atr >= row['close']:
                    renko.loc[len(renko)] = [row['date'], prev_open, prev_open - atr]
                    prev_open = prev_open - atr
            else:
                while prev_close - atr >= row['close']:
                    renko.loc[len(renko)] = [row['date'], prev_close, prev_close - atr]
                    prev_open = prev_close
                    prev_close = prev_close - atr
                while prev_open + atr <= row['close']:
                    renko.loc[len(renko)] = [row['date'], prev_open, prev_open + atr]
                    prev_open = prev_open + atr
                    
        renko['renko_ema13'] = ta.EMA(renko,timeperiod=13, price='renko_open')

        renko.dropna(inplace=True)
        return renko.groupby('date').last()

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        if (dataframe['date'].max() - dataframe['date'].min()).days < self.min_days:
            dataframe['buy'] = 0
            return dataframe

        try:
            if self.dp:
                if self.dp.runmode in (RunMode.LIVE, RunMode.DRY_RUN):
                    ticker_data = self.dp._exchange.get_ticker(metadata['pair'])
                    symbol,bid,ask,last= ticker_data['symbol'],ticker_data['bid'],ticker_data['ask'],ticker_data['last']
                    
                    if(ask <=0 or bid <=0 or last <= 0):
                        dataframe['buy'] = 0
                        return dataframe

                    spread = ((ask - bid)/last) * 100
                    if(spread > 0.20):
                        dataframe['buy'] = 0
                        return dataframe
        except:
            print(f"could not get ticker for pair: {metadata['pair']}")
            dataframe['buy'] = 0
            return dataframe

        dataframe.loc[
            (
                (
                    (dataframe['renko_ema13'] < dataframe['renko_open']) &
                    (dataframe['renko_open'] < dataframe['renko_close'])
                )
            ),
            'buy'] = 1

        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        if (dataframe['date'].max() - dataframe['date'].min()).days < self.min_days:
            dataframe['sell'] = 0
            return dataframe

        dataframe.loc[
            (
                 (dataframe['renko_open'] > dataframe['renko_close']) 
            ),
            'sell'] = 1
        return dataframe
