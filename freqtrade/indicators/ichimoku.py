import pandas as pd
from pandas import DataFrame


def ichimoku(dataframe: DataFrame, tenkan_sen_window=9, kijun_sen_window=26, senkou_span_offset=26, senkou_span_b_window=52, chikou_span_offset=26) -> DataFrame:
    
    ichimoku_df = pd.DataFrame(index=dataframe.index.copy())

    high = dataframe['high'].rolling(window=tenkan_sen_window).max()
    low = dataframe['low'].rolling(window=tenkan_sen_window).min()
    ichimoku_df['tenkan_sen'] = (high + low) / 2

    # Kijun-sen (Base Line): (26-period high + 26-period low)/2))
    high = dataframe['high'].rolling(window=kijun_sen_window).max()
    low = dataframe['low'].rolling(window=kijun_sen_window).min()
    ichimoku_df['kijun_sen'] = (high + low) /2

    # Senkou Span A (Leading Span A): (Conversion Line + Base Line)/2))
    #df['senkou_span_a-26'] = ((df['tenkan_sen'] + df['kijun_sen']) / 2)
    ichimoku_df['senkou_span_a'] = ((ichimoku_df['tenkan_sen'] + ichimoku_df['tenkan_sen']) / 2).shift(senkou_span_offset)

    # Senkou Span B (Leading Span B): (52-period high + 52-period low)/2))
    high = dataframe['high'].rolling(window=senkou_span_b_window).max()
    low = dataframe['low'].rolling(window=senkou_span_b_window).min()
    #df['senkou_span_b-26'] = ((high_52 + low_52) /2)
    ichimoku_df['senkou_span_b'] = ((high + low) /2).shift(senkou_span_offset)

    # The most current closing price plotted 26 time periods behind (optional)
    ichimoku_df['chikou_span'] = dataframe['close'].shift(-chikou_span_offset) # 26 according to investopedia

    return ichimoku_df