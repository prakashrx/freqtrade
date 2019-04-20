# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement

import talib.abstract as ta
import pandas as pd
from pandas import DataFrame

import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.indicator_helpers import fishers_inverse
from freqtrade.strategy.interface import IStrategy


class Ichimoku(IStrategy):

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        #optimized for 4H window
        #self.ichimoku(dataframe, '', tenkan_sen_window=15, kijun_sen_window=27, senkou_span_offset=15, senkou_span_b_window=50)
        #self.ichimoku(dataframe, 'sell_', tenkan_sen_window=13, kijun_sen_window=15)
        self.ichimoku(dataframe, '', tenkan_sen_window=7, kijun_sen_window=19, senkou_span_offset=34, senkou_span_b_window=62)
        self.ichimoku(dataframe, 'sell_', tenkan_sen_window=15, kijun_sen_window=31)

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
        df[prefix + 'senkou_span_a'] = ((df['tenkan_sen'] + df['kijun_sen']) / 2).shift(senkou_span_offset)

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
        dataframe.loc[
            (
                (
                    #(dataframe['close'] > dataframe['open']) &
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
        """
        Based on TA indicators, populates the sell signal for the given dataframe
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with buy column
        """
        dataframe.loc[
            (
                qtpylib.crossed_below(dataframe['sell_tenkan_sen'], dataframe['sell_kijun_sen'])
            ),
            'sell'] = 1
        return dataframe
