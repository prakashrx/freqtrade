# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement

import talib.abstract as ta
from pandas import DataFrame
from typing import Dict, Any, Callable, List
from functools import reduce

from skopt.space import Categorical, Dimension, Integer, Real

import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.optimize.hyperopt_interface import IHyperOpt

class_name = 'IchimokuOpts'


class IchimokuOpts(IHyperOpt):
    """
    Default hyperopt provided by freqtrade bot.
    You can override it with your own hyperopt
    """

    @staticmethod
    def populate_indicators(dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['rsi'] = ta.RSI(dataframe)
        
        for i in range(3, 81):
            high = dataframe['high'].rolling(window=i).max()
            low = dataframe['low'].rolling(window=i).min()
            dataframe['high_low_' + str(i)] = (high + low) / 2

        #4H
        # IchimokuOpts.ichimoku(dataframe, '', tenkan_sen_window=15, kijun_sen_window=27, senkou_span_offset=15, senkou_span_b_window=50)
        # IchimokuOpts.ichimoku(dataframe, 'sell_', tenkan_sen_window=13, kijun_sen_window=15)
        IchimokuOpts.ichimoku(dataframe, '', tenkan_sen_window=15, kijun_sen_window=29, senkou_span_offset=30, senkou_span_b_window=62)
        IchimokuOpts.ichimoku(dataframe, 'sell_', tenkan_sen_window=13, kijun_sen_window=20)

        #1H
        #IchimokuOpts.ichimoku(dataframe, '', tenkan_sen_window=11, kijun_sen_window=18, senkou_span_offset=15, senkou_span_b_window=70)
        #IchimokuOpts.ichimoku(dataframe, 'sell_', tenkan_sen_window=6, kijun_sen_window=23)
        return dataframe

    @staticmethod
    def ichimoku(df: DataFrame, prefix='', tenkan_sen_window=9, kijun_sen_window=26, senkou_span_offset=26, senkou_span_b_window=52, chikou_span_offset=26) -> DataFrame:
        
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

    @staticmethod
    def buy_strategy_generator(params: Dict[str, Any]) -> Callable:
        """
        Define the buy strategy parameters to be used by hyperopt
        """
        def populate_buy_trend(dataframe: DataFrame, metadata: dict) -> DataFrame:
            """
            Buy strategy Hyperopt will build and use
            """
            tenkan_sen = dataframe['high_low_' + str(params['tenkan_sen_window'])]
            kijun_sen = dataframe['high_low_' + str(params['kijun_sen_window'])]
            senkou_span_a = ((tenkan_sen + kijun_sen)/2).shift(params['senkou_span_offset'])
            senkou_span_b = dataframe['high_low_' + str(params['senkou_span_b_window'])].shift(params['senkou_span_offset'])

            dataframe.loc[
            (
                (
                    (qtpylib.crossed_above(tenkan_sen, kijun_sen)) &
                    (dataframe['open'] > senkou_span_a) &
                    (dataframe['open'] > senkou_span_b)
                ) 
            ),
            'buy'] = 1

            return dataframe

        return populate_buy_trend

    @staticmethod
    def indicator_space() -> List[Dimension]:
        """
        Define your Hyperopt space for searching strategy parameters
        """

        return [
            Integer(5, 15, name='tenkan_sen_window'),
            Integer(15, 35, name='kijun_sen_window'),
            Integer(15, 35, name='senkou_span_offset'),
            Integer(45, 70, name='senkou_span_b_window')
        ]

    @staticmethod
    def sell_strategy_generator(params: Dict[str, Any]) -> Callable:
        """
        Define the sell strategy parameters to be used by hyperopt
        """
        def populate_sell_trend(dataframe: DataFrame, metadata: dict) -> DataFrame:
            """
            Sell strategy Hyperopt will build and use
            """
            
            tenkan_sen = dataframe['high_low_' + str(params['sell_tenkan_sen_window'])]
            kijun_sen = dataframe['high_low_' + str(params['sell_kijun_sen_window'])]

            dataframe.loc[
            (
                qtpylib.crossed_below(tenkan_sen, kijun_sen)
            ),
            'sell'] = 1
            return dataframe

        return populate_sell_trend

    @staticmethod
    def sell_indicator_space() -> List[Dimension]:
        """
        Define your Hyperopt space for searching sell strategy parameters
        """
        return [
                Integer(5, 15, name='sell_tenkan_sen_window'),
                Integer(15, 35, name='sell_kijun_sen_window')
               ]

    @staticmethod
    def generate_roi_table(params: Dict) -> Dict[int, float]:
        """
        Generate the ROI table that will be used by Hyperopt
        """
        roi_table = {}
        roi_table[0] = params['roi_p1'] + params['roi_p2'] + params['roi_p3']
        roi_table[params['roi_t3']] = params['roi_p1'] + params['roi_p2']
        roi_table[params['roi_t3'] + params['roi_t2']] = params['roi_p1']
        roi_table[params['roi_t3'] + params['roi_t2'] + params['roi_t1']] = 0

        return roi_table

    @staticmethod
    def stoploss_space() -> List[Dimension]:
        """
        Stoploss Value to search
        """
        return [
            Real(-0.1, -0.02, name='stoploss'),
        ]

    @staticmethod
    def roi_space() -> List[Dimension]:
        """
        Values to search for each ROI steps
        """
        return [
            Integer(10, 120, name='roi_t1'),
            Integer(10, 60, name='roi_t2'),
            Integer(10, 40, name='roi_t3'),
            Real(0.01, 0.04, name='roi_p1'),
            Real(0.01, 0.07, name='roi_p2'),
            Real(0.01, 0.20, name='roi_p3'),
        ]

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators. Should be a copy of from strategy
        must align to populate_indicators in this file
        Only used when --spaces does not include buy
        """

        dataframe.loc[
            (
                (
                    #(qtpylib.crossed_above(dataframe['tenkan_sen'], dataframe['kijun_sen'])) &
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
        Based on TA indicators. Should be a copy of from strategy
        must align to populate_indicators in this file
        Only used when --spaces does not include sell
        """

        dataframe.loc[
            (
                qtpylib.crossed_below(dataframe['sell_tenkan_sen'], dataframe['sell_kijun_sen'])
            ),
            'sell'] = 1
        return dataframe
