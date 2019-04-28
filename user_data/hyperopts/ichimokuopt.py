# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement

import talib.abstract as ta
from pandas import DataFrame
from typing import Dict, Any, Callable, List
from functools import reduce

from skopt.space import Categorical, Dimension, Integer, Real

import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.optimize.hyperopt_interface import IHyperOpt
from freqtrade.strategy.util import resample_to_interval, resampled_merge
import freqtrade.indicators as indicators

class_name = 'IchimokuOpts'



class IchimokuOpts(IHyperOpt):
    """
    Default hyperopt provided by freqtrade bot.
    You can override it with your own hyperopt
    """

    dataframes = {}

    @staticmethod
    def populate_indicators(dataframe: DataFrame, metadata: dict) -> DataFrame:

        for i in range(3, 81):
            high = dataframe['high'].rolling(window=i).max()
            low = dataframe['low'].rolling(window=i).min()
            dataframe['high_low_' + str(i)] = (high + low) / 2

        #Default time interval
        #indicators - Hikenashi Macd
        macd = ta.MACD(dataframe, fastperiod=14, slowperiod=27, signalperiod=9)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']

        #Daily interval
        #indicators - Macd
        dataframe_1d =  resample_to_interval(dataframe, '1d')
        IchimokuOpts.dataframes[metadata['pair']] = dataframe_1d

        macd = ta.MACD(dataframe_1d, fastperiod=14, slowperiod=27, signalperiod=15)
        dataframe_1d['macd_1d'] = macd['macd']
        dataframe_1d['macdsignal_1d'] = macd['macdsignal']
        dataframe_1d['macdhist_1d'] = macd['macdhist']
        dataframe_1d['macdhist_1d'] = macd['macdhist']


        #Daily interval
        #indicators - Ichimoku cloud, Macd
        dataframe_4h =  resample_to_interval(dataframe, '4h')
        ichimoku = indicators.ichimoku(dataframe_4h, tenkan_sen_window=15, kijun_sen_window=27, senkou_span_offset=15, senkou_span_b_window=50)
        dataframe_4h['tenkan_sen_4h'] = ichimoku['tenkan_sen']
        dataframe_4h['kijun_sen_4h'] = ichimoku['kijun_sen']
        dataframe_4h['senkou_span_a_4h'] = ichimoku['senkou_span_a']
        dataframe_4h['senkou_span_b_4h'] = ichimoku['senkou_span_b']
        macd = ta.MACD(dataframe_4h, fastperiod=14, slowperiod=27, signalperiod=9)
        dataframe_4h['macd_4h'] = macd['macd']
        dataframe_4h['macdsignal_4h'] = macd['macdsignal']

        dataframe = resampled_merge(dataframe, dataframe_4h)
        dataframe = resampled_merge(dataframe, dataframe_1d)

        return dataframe

    @staticmethod
    def buy_strategy_generator(params: Dict[str, Any]) -> Callable:

        def populate_buy_trend(dataframe: DataFrame, metadata: dict) -> DataFrame:
            
            # tenkan_sen = dataframe['high_low_' + str(params['tenkan_sen_window'])]
            # kijun_sen = dataframe['high_low_' + str(params['kijun_sen_window'])]
            # senkou_span_a = ((tenkan_sen + kijun_sen)/2).shift(params['senkou_span_offset'])
            # senkou_span_b = dataframe['high_low_' + str(params['senkou_span_b_window'])].shift(params['senkou_span_offset'])

            dataframe['buy'] = 0
            return dataframe

        return populate_buy_trend

    @staticmethod
    def indicator_space() -> List[Dimension]:
        """
        Define your Hyperopt space for searching strategy parameters
        """

        return [
            # Integer(5, 52, name='tenkan_sen_window'),
            # Integer(5, 52, name='kijun_sen_window'),
            # Integer(5, 52, name='senkou_span_offset'),
            # Integer(5, 70, name='senkou_span_b_window')
        ]

    @staticmethod
    def sell_strategy_generator(params: Dict[str, Any]) -> Callable:

        cache = {}

        def populate_sell_trend(dataframe: DataFrame, metadata: dict) -> DataFrame:


            if(params['macd_1d_fast'] >= params['macd_1d_slow']):
                dataframe['sell'] = 0
                return dataframe

            key = f"macd_1d_{metadata['pair']}_{params['macd_1d_fast']}_{params['macd_1d_slow']}_{params['macd_1d_signal']}_sell"
            dataframe_1d = IchimokuOpts.dataframes[metadata['pair']]

            if key not in cache:
                macd = ta.MACD(dataframe_1d, fastperiod=params['macd_1d_fast'], slowperiod=params['macd_1d_slow'], signalperiod=params['macd_1d_signal'])
                macd.loc[( macd['macd'] < macd['macdsignal'] ), 'sell'] = 1
                cache[key] = macd['sell']
            
            dataframe_1d["sell_cache"] = cache[key]
            df2 = resampled_merge(dataframe,dataframe_1d)
            df2['sell'] = 0
            dataframe['sell'] = df2["sell_cache"]

            return dataframe

        return populate_sell_trend

    @staticmethod
    def sell_indicator_space() -> List[Dimension]:
        """
        Define your Hyperopt space for searching sell strategy parameters
        """
        return [
                Integer(5, 20, name='macd_1d_fast'),
                Integer(20, 52, name='macd_1d_slow'),
                Integer(5, 30, name='macd_1d_signal')
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
            Integer(10, 500, name='roi_t1'),
            Integer(300, 1500, name='roi_t2'),
            Integer(1000, 5000, name='roi_t3'),
            Real(0.01, 0.04, name='roi_p1'),
            Real(0.01, 0.07, name='roi_p2'),
            Real(0.01, 0.20, name='roi_p3'),
        ]

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # if (dataframe['date'].max() - dataframe['date'].min()).days < 30:
        #     dataframe['buy'] = 0
        #     return dataframe

        dataframe.loc[
            (
                (
                    (dataframe['macd'] > dataframe['macdsignal']) &
                    #(dataframe['macd_4h'] > dataframe['macdsignal_4h']) &
                    (dataframe['macd_1d'] > dataframe['macdsignal_1d']) &
                    (dataframe['tenkan_sen_4h'] > dataframe['kijun_sen_4h']) &
                    (dataframe['open'] > dataframe['senkou_span_a_4h']) &
                    (dataframe['open'] > dataframe['senkou_span_b_4h']) &
                    (dataframe['close'] > dataframe['senkou_span_a_4h']) &
                    (dataframe['close'] > dataframe['senkou_span_b_4h'])
                )
            ),
            'buy'] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                #qtpylib.crossed_below(dataframe['macd_4h'], dataframe['macdsignal_4h']) |   #in bear market this performs well
                (dataframe['macd_1d'] < dataframe['macdsignal_1d'])
                #(dataframe['ha_close_1d'] < dataframe['ha_open_1d'].shift())
            ),
            'sell'] = 1
        return dataframe
