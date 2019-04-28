# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement

import talib.abstract as ta
import pandas as pd
from pandas import DataFrame

import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.indicator_helpers import fishers_inverse
from freqtrade.strategy.interface import IStrategy
from freqtrade.state import RunMode
from freqtrade.strategy.util import resample_to_interval, resampled_merge

class Ichimoku1(IStrategy):

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        #1H
        macd = ta.MACD(dataframe, fastperiod=14, slowperiod=27, signalperiod=9)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        heikinashi = qtpylib.heikinashi(dataframe)
        dataframe['ha_open'] = heikinashi['open']
        dataframe['ha_close'] = heikinashi['close']
        dataframe['ha_high'] = heikinashi['high']
        dataframe['ha_low'] = heikinashi['low']
        self.ichimoku(dataframe, '', tenkan_sen_window=15, kijun_sen_window=27, senkou_span_offset=15, senkou_span_b_window=50)
        self.ichimoku(dataframe, 'sell_', tenkan_sen_window=13, kijun_sen_window=15)

        #4H
        dataframe_4h = resample_to_interval(dataframe, '4h')
        dataframe_4h['open_4h'] = dataframe_4h['open']
        dataframe_4h['close_4h'] = dataframe_4h['close']
        dataframe_4h['high_4h'] = dataframe_4h['high']
        dataframe_4h['low_4h'] = dataframe_4h['low']

        self.ichimoku(dataframe_4h, '', '_4h', tenkan_sen_window=15, kijun_sen_window=27, senkou_span_offset=15, senkou_span_b_window=50)
        self.ichimoku(dataframe_4h, 'sell_', '_4h', tenkan_sen_window=13, kijun_sen_window=15)

        macd = ta.MACD(dataframe_4h, fastperiod=14, slowperiod=27, signalperiod=9)
        dataframe_4h['macd_4h'] = macd['macd']
        dataframe_4h['macdsignal_4h'] = macd['macdsignal']
        heikinashi = qtpylib.heikinashi(dataframe_4h)
        dataframe_4h['ha_open_4h'] = heikinashi['open']
        dataframe_4h['ha_close_4h'] = heikinashi['close']
        dataframe_4h['ha_high_4h'] = heikinashi['high']
        dataframe_4h['ha_low_4h'] = heikinashi['low']

        #1D
        dataframe_1d =  resample_to_interval(dataframe, '1d')
        heikinashi = qtpylib.heikinashi(dataframe_1d)
        dataframe_1d['open'] = heikinashi['open']
        dataframe_1d['close'] = heikinashi['close']
        dataframe_1d['high'] = heikinashi['high']
        dataframe_1d['low'] = heikinashi['low']

        dataframe_1d['mfi_1d'] = ta.MFI(dataframe_1d)
        macd = ta.MACD(dataframe_1d, fastperiod=14, slowperiod=27, signalperiod=9)
        dataframe_1d['macd_1d'] = macd['macd']
        dataframe_1d['macdsignal_1d'] = macd['macdsignal']

        dataframe = resampled_merge(dataframe, dataframe_4h)
        dataframe = resampled_merge(dataframe, dataframe_1d)
 
        return dataframe

    def ichimoku(self, df: DataFrame, prefix='', sufix='', tenkan_sen_window=9, kijun_sen_window=26, senkou_span_offset=26, senkou_span_b_window=52, chikou_span_offset=26) -> DataFrame:
        
        high = df['high'].rolling(window=tenkan_sen_window).max()
        low = df['low'].rolling(window=tenkan_sen_window).min()
        tenken_sen = (high + low) / 2
        df[prefix + 'tenkan_sen' + sufix] = tenken_sen

        # Kijun-sen (Base Line): (26-period high + 26-period low)/2))
        high = df['high'].rolling(window=kijun_sen_window).max()
        low = df['low'].rolling(window=kijun_sen_window).min()
        kijun_sen = (high + low) /2
        df[prefix + 'kijun_sen'+ sufix] = kijun_sen

        # Senkou Span A (Leading Span A): (Conversion Line + Base Line)/2))
        #df['senkou_span_a-26'] = ((df['tenkan_sen'] + df['kijun_sen']) / 2)
        df[prefix + 'senkou_span_a' + sufix] = ((tenken_sen + kijun_sen) / 2).shift(senkou_span_offset)

        # Senkou Span B (Leading Span B): (52-period high + 52-period low)/2))
        high = df['high'].rolling(window=senkou_span_b_window).max()
        low = df['low'].rolling(window=senkou_span_b_window).min()
        #df['senkou_span_b-26'] = ((high_52 + low_52) /2)
        df[prefix + 'senkou_span_b' + sufix] = ((high + low) /2).shift(senkou_span_offset)

        # The most current closing price plotted 26 time periods behind (optional)
        df[prefix + 'chikou_span' + sufix] = df['close'].shift(-chikou_span_offset) # 26 according to investopedia

        return df

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
 

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
                    # (dataframe['mfi_1d'] < 80) &
                    (dataframe['macd_1d'] > dataframe['macdsignal_1d']) &
                    (dataframe['tenkan_sen_4h'] > dataframe['kijun_sen_4h']) &
                    (dataframe['open_4h'] > dataframe['senkou_span_a_4h']) &
                    (dataframe['open_4h'] > dataframe['senkou_span_b_4h']) &
                    (dataframe['close_4h'] > dataframe['senkou_span_a_4h']) &
                    (dataframe['close_4h'] > dataframe['senkou_span_b_4h']) &
                    (dataframe['macd'] > dataframe['macdsignal']) 
                    # (dataframe['ha_high'] > dataframe['ha_high'].shift()) &
                    # (dataframe['ha_close'] > dataframe['ha_close'].shift()) &
                    # (dataframe['ha_high_4h'] > dataframe['ha_high_4h'].shift()) &
                    # (dataframe['ha_close_4h'] > dataframe['ha_close_4h'].shift())
                )
            ),
            'buy'] = 1

        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                    # (
                    #     (dataframe['mfi_1d'] > 80) & 
                    #     (dataframe['mfi_1d'] < dataframe['mfi_1d'].shift())
                    # ) |
                    #(dataframe['macd_1d'] < dataframe['macdsignal_1d']) |
                    #(dataframe['sell_tenkan_sen'] < dataframe['sell_kijun_sen'])
                    (dataframe['macd_1d'] < dataframe['macdsignal_1d']) 
                    # (
                    #     (dataframe['ha_high'] < dataframe['ha_high'].shift()) & 
                    #     (dataframe['ha_close'] < dataframe['ha_close'].shift())
                    # ) |
                    # (
                    #     (dataframe['ha_high_4h'] < dataframe['ha_high_4h'].shift()) & 
                    #     (dataframe['ha_close_4h'] < dataframe['ha_close_4h'].shift())
                    # )
            ),
            'sell'] = 1
        return dataframe
