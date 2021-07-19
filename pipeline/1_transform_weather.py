# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.11.3
#   kernelspec:
#     display_name: 'Python 3.7.9 64-bit (''.venv'': venv)'
#     name: python3
# ---

# %%
import datetime as dt
import requests
import time
import pandas as pd
import glob
import numpy as np
import os



# %%
### SCRIPT CELL - DON'T RUN IN NOTEBOOK


def run() :
    # change working directory to where this file lives
    os.chdir(os.path.dirname(os.path.abspath(__file__)))



    # %%
    # TODO: Generate past 7 days features

    # %%
    # read weather history
    # list all files that are to be concatenated
    flist = list()
    for filepath in glob.iglob('data/0_raw/weather/*.csv'):
        flist.append(filepath)

    # this sorts the original list in place
    flist.sort()
    #print(flist)


    # initialize weather with the first file
    weather = pd.read_csv(flist[0])
    #remove last line because it's duplicated in the first line of next file
    weather = weather.iloc[0:-1]

    for f in flist[1:]:
        #remove last line because it's duplicated in thhe first line of next file
        df = pd.read_csv(f)
        df = df.iloc[0:-1]
        weather = pd.concat([weather, df])


    # %%
    # read forecast
    fc = pd.read_csv('data/0_raw/weather_forecast/forecast.csv')
    fc['Minimum Temperature'] = fc['Temperature']
    fc['Maximum Temperature'] = fc['Temperature']

    # Precipitation / Niederschlag is given in Chance% and Amount (Precipitation)
    # in real historic data there's no chance - either it rains or not
    # therefore we assume if chance > 50% it does rain otherwise not
    fc['cp'] = fc['Chance Precipitation (%)'].apply(lambda x: 1 if x >= 0.5 else 0)
    fc['Precipitation'] = fc['Precipitation']*fc['cp']

    # These columns are in fc but not in weather, therefore drop
    fc = fc.drop(['Chance Precipitation (%)', 'Snow', 'cp'], axis=1)

    # These columns are in weather but not in forecast therefore we drop
    weather = weather.drop(['Dew Point', 'Info', 'Precipitation Cover', 'Visibility', 'Weather Type'], axis=1)


    # %%
    pd.to_datetime(fc['Date time']).min(), pd.to_datetime(weather['Date time']).max()

# %%

    # sort forecast the same way as weather
    fc = fc[weather.columns]
    assert (weather.columns == fc.columns).all(), 'fc and weather must have the same columns in the same order'

# %%

    # allow for max 2 hours overlap or gap
    assert pd.to_datetime(fc['Date time']).min() - dt.timedelta(hours=3) < pd.to_datetime(weather['Date time']).max(), 'forecast should start exactly where history ends'
    assert  pd.to_datetime(weather['Date time']).max() + dt.timedelta(hours=3) > pd.to_datetime(fc['Date time']).min(), 'forecast should start exactly where history ends'
    weather = pd.concat([weather, fc])


    # %%
    weather = weather.reset_index().drop('index', axis=1)
    #test = weather.groupby('Date time').count().Temperature.reset_index()
    #test[test.Temperature>1]

    # %%
    # test if there's only one unique entry for every datetime
    assert len(weather['Date time'].unique()) == len(weather)

    # %%
    # Aggregate to one row per day
    weather['date'] = weather['Date time'].apply(lambda x: dt.datetime.strptime(x, '%m/%d/%Y %H:%M:%S').date())
    weather = weather.groupby('date').agg(
    {
        #"Address":  np.min #(pd.core.groupby.GroupBy.nth, 0)
        "Minimum Temperature": np.min
        , "Maximum Temperature": np.max
        , "Temperature": np.mean
        
    #   , "Dew Point": np.mean
        , "Relative Humidity": np.mean
        , "Heat Index": np.mean

        , "Wind Speed": np.mean
        , "Wind Gust": np.mean
        , "Wind Direction": np.mean
        , "Wind Chill": np.mean

        , "Precipitation": np.mean
    #   , "Precipitation Cover": np.mean
        , "Snow Depth": np.mean
    #   , "Visibility": np.mean
        , "Cloud Cover": np.mean

        #, "Sea Level Pressure": np.mean
        #, "Weather Type": (pd.core.groupby.GroupBy.nth, 0)
        #, "Latitude": (pd.core.groupby.GroupBy.nth, 0)
        #, "Longitude": (pd.core.groupby.GroupBy.nth, 0)
        #, "Resolved Address": (pd.core.groupby.GroupBy.nth, 0)
        #, "Name": (pd.core.groupby.GroupBy.nth, 0)
        #, "Info": (pd.core.groupby.GroupBy.nth, 0)
        #, "Conditions": np.min
    })

    # %%
    # drop last (forecast) day
    weather = weather[:-1]

    # %%
    weather.reset_index().reset_index()

    # %%
    # now we have cleaned weather history, write it to file
    weather.reset_index().reset_index().to_csv('data/1_trans/weather.csv', index=False)

# %%

# %%
### SCRIPT CELL - DON'T RUN IN NOTEBOOK

if __name__ == '__main__':
    # run this step
    run()
