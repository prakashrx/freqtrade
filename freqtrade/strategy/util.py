from pandas import DatetimeIndex, merge, DataFrame, to_datetime, DateOffset

TICKER_INTERVAL_MINUTES = {
    '1m': 1,
    '5m': 5,
    '15m': 15,
    '30m': 30,
    '1h': 60,
    '60m': 60,
    '2h': 120,
    '4h': 240,
    '6h': 360,
    '8h': 480,
    '12h': 720,
    '1d': 1440,
    '1w': 10080,
}

def resample_to_interval(dataframe, interval):
    if isinstance(interval, str):
        interval = TICKER_INTERVAL_MINUTES[interval]

    """
        resamples the given dataframe to the desired interval. Please be aware you need to upscale this to join the results
        with the other dataframe
    :param dataframe: dataframe containing close/high/low/open/volume
    :param interval: to which ticker value in minutes would you like to resample it
    :return:
    """

    df = dataframe.copy()
    df = df.set_index(DatetimeIndex(df['date']))
    ohlc_dict = {
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }
    df = df.resample(str(interval) + 'min',
                     label="right").agg(ohlc_dict).dropna()
    df['date'] = df.index

    return df


def resampled_merge(original, resampled, fill_na = True):
    """
    this method merges a resampled dataset back into the orignal data set
    :param original: the original non resampled dataset
    :param resampled:  the resampled dataset
    :return: the merged dataset
    """

    interval = int((original['date'] - original['date'].shift()).min().seconds / 60)
    resampled_interval = compute_interval(resampled)
    # no point in interpolating these colums
    resampled = resampled.drop(columns=['date', 'volume'])

    # rename all the colums to the correct interval
    # for header in list(resampled):
    #     # store the resampled columns in it
    #     resampled['resample_{}_{}'.format(resampled_interval, header)] = resampled[header]

    # drop columns which should not be joined
    resampled = resampled.drop(columns=['open', 'high', 'low', 'close'])

    resampled['date'] = resampled.index - DateOffset(minutes=interval)
    resampled.index = range(len(resampled))
    dataframe = merge(original, resampled, on='date', how='left')

    if fill_na:
        dataframe.fillna(method='ffill', inplace=True)
    return dataframe

def compute_interval(dataframe: DataFrame, exchange_interval=True):
    """
        calculates the interval of the given dataframe for us
    :param dataframe:
    :param exchange_interval: should we convert the result to an exchange interval or just a number
    :return:
    """
    resampled_interval = int((dataframe['date'] - dataframe['date'].shift()).min().seconds / 60)

    if exchange_interval:
        converted = list(TICKER_INTERVAL_MINUTES.keys())[
            list(TICKER_INTERVAL_MINUTES.values()).index(exchange_interval)]
        if len(converted) > 0:
            return converted
        else:
            raise Exception(
                "sorry, your interval of {} is not supported in {}".format(resampled_interval, TICKER_INTERVAL_MINUTES))

    return resampled_interval