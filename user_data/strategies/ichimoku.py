# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
import logging
import talib.abstract as ta
import pandas as pd
from pandas import DataFrame
import arrow
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.indicator_helpers import fishers_inverse
from freqtrade.strategy.interface import IStrategy
from freqtrade.state import RunMode
from freqtrade.strategy.util import resample_to_interval, resampled_merge
from freqtrade.data.history import parse_ticker_dataframe

logger = logging.getLogger("IchimokuStrategy")

class Ichimoku(IStrategy):

    cache = {}

    def get_extend_historical(self, pair: str, dataframe: DataFrame) -> DataFrame:
        if self.dp and self.dp.runmode in (RunMode.LIVE, RunMode.DRY_RUN):
            if pair not in self.cache:
                logger.info(f"Downloading historical ohlc for pair: {pair})")
                hist = self.dp._exchange.get_history(pair=pair, ticker_interval=self.ticker_interval,
                                            since_ms=int(arrow.utcnow().shift(days=-60).float_timestamp) * 1000)
                self.cache[pair] = parse_ticker_dataframe(hist,self.ticker_interval)
            hist_df = self.cache[pair]
            min_date = dataframe['date'].min()
            return pd.concat([ hist_df[hist_df['date'] < min_date] , dataframe ])
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        

        dataframe = self.get_extend_historical(metadata['pair'], dataframe)

        #optimized for 4H window
        self.ichimoku(dataframe, '', tenkan_sen_window=15, kijun_sen_window=27, senkou_span_offset=15, senkou_span_b_window=50)
        self.ichimoku(dataframe, 'sell_', tenkan_sen_window=9, kijun_sen_window=15)

        macd = ta.MACD(dataframe, fastperiod=14, slowperiod=27, signalperiod=9)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        
        dataframe_1d =  resample_to_interval(dataframe, '1d')
        macd = ta.MACD(dataframe_1d, fastperiod=14, slowperiod=27, signalperiod=9)
        dataframe_1d['macd_1d'] = macd['macd']
        dataframe_1d['macdsignal_1d'] = macd['macdsignal']
        
        dataframe_4h =  resample_to_interval(dataframe, '1d')
        macd = ta.MACD(dataframe_4h, fastperiod=14, slowperiod=27, signalperiod=9)
        dataframe_4h['macd_4h'] = macd['macd']
        dataframe_4h['macdsignal_4h'] = macd['macdsignal']

        dataframe = resampled_merge(dataframe, dataframe_4h)
        dataframe = resampled_merge(dataframe, dataframe_1d)

        return dataframe

    def ichimoku(self, df: DataFrame, prefix='', tenkan_sen_window=9, kijun_sen_window=26, senkou_span_offset=26, senkou_span_b_window=52, chikou_span_offset=26) -> DataFrame:
        
        high = df['high'].rolling(window=tenkan_sen_window).max()
        low = df['low'].rolling(window=tenkan_sen_window).min()
        df[prefix + 'tenkan_sen'] = (high + low) / 2

        # Kijun-sen (Base Line): (26-period high + 26-period low)/2))
        high = df['high'].rolling(window=kijun_sen_window).max()
        low = df['low'].rolling(window=kijun_sen_window).min()
        df[prefix + 'kijun_sen'] = (high + low) /2

        # Senkou Span A (Leading Span A): (Conversion Line + Base Line)/2))
        #df['senkou_span_a-26'] = ((df['tenkan_sen'] + df['kijun_sen']) / 2)
        df[prefix + 'senkou_span_a'] = ((df[prefix + 'tenkan_sen'] + df[prefix + 'kijun_sen']) / 2).shift(senkou_span_offset)

        # Senkou Span B (Leading Span B): (52-period high + 52-period low)/2))
        high = df['high'].rolling(window=senkou_span_b_window).max()
        low = df['low'].rolling(window=senkou_span_b_window).min()
        #df['senkou_span_b-26'] = ((high_52 + low_52) /2)
        df[prefix + 'senkou_span_b'] = ((high + low) /2).shift(senkou_span_offset)

        # The most current closing price plotted 26 time periods behind (optional)
        df[prefix + 'chikou_span'] = df['close'].shift(-chikou_span_offset) # 26 according to investopedia

        return df

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the buy signal for the given dataframe
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with buy column
        """
        if (dataframe['date'].max() - dataframe['date'].min()).days < 30:
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
                    (dataframe['macd'] > dataframe['macdsignal']) &
                    (dataframe['macd_1d'] > dataframe['macdsignal_1d']) &
                    (dataframe['tenkan_sen'] > dataframe['kijun_sen']) &
                    (dataframe['open'] > dataframe['senkou_span_a']) &
                    (dataframe['open'] > dataframe['senkou_span_b']) &
                    (dataframe['close'] > dataframe['senkou_span_a']) &
                    (dataframe['close'] > dataframe['senkou_span_b'])
                )
            ),
            'buy'] = 1

        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        

        dataframe.loc[
            (
                qtpylib.crossed_below(dataframe['macd_1d'], dataframe['macdsignal_1d']) 
            ),
            'sell'] = 1
        return dataframe
