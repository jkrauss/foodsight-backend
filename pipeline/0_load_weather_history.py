# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.11.4
#   kernelspec:
#     display_name: 'Python 3.7.9 64-bit (''.venv'': venv)'
#     name: python3
# ---

# %%
import datetime as dt
import requests
import time
import pandas as pd
import os
import glob

import util
config = util.load_config()

# %%
### SCRIPT CELL - DON'T RUN IN NOTEBOOK


def run() :
    # change working directory to where this file lives
    os.chdir(config['base']['pipeline_path'])



    # %%
    url = "https://visual-crossing-weather.p.rapidapi.com/history"

    querystring = {
        "startDateTime":"2018-04-01T00:00:00",
        "aggregateHours":"1"
        ,"location":"50.0826,8.2493",
        "endDateTime":"2018-04-20T00:00:00"
        ,"unitGroup":"metric"
        ,"contentType":"csv"
        ,"shortColumnNames":"0"
        }

    headers = {
        'x-rapidapi-key': "0775822d7dmshcc59ba9c3899f48p1c5f41jsn6c9e54ea8866",
        'x-rapidapi-host': "visual-crossing-weather.p.rapidapi.com"
        }

    # %%
    # determine the last existing weather-file
    flist = list()
    for filepath in glob.iglob('data/0_raw/weather/*.csv'):
        flist.append(filepath)

    # this sorts the original list in place
    flist.sort()

    # extract year, month, date from last filename 
    y,m,d = flist[-1].split('_')[2].split('-')
    y,m,d = int(y),int(m),int(d)


# %%

    # how many days go into 1 file? ... delat=20 loads 21 days
    delta = dt.timedelta(days=20)

    # if there's more than delta time in the last file, we replace it and start a new one
    # this takes two requests
    # otherwise we only replace the last file with one request
    if dt.date.today() - dt.date(y,m,d) >= delta :
        num_requests = 2
    else:
        num_requests = 1
    num_requests


    # %%
    # start reading weather data into files from this date
    # !!ATTENTION!! In order to receive a consistent weather history always choose a start date that is the same as an existing one!
    start_dt = dt.datetime(y,m,d,0,0,0)

    # ATTENTION! There's a limit of 500 requests per MONTH on the API - use very carefully!
    # There's also a limit of 500 lines per API call - this gives a max of 21 days * 24 hours (21 is too much)
    for i in range(num_requests):
        end_dt=start_dt+delta
        start_str = dt.datetime.strftime(start_dt, "%Y-%m-%dT%H:%M:%S")
        end_str = dt.datetime.strftime(end_dt, "%Y-%m-%dT%H:%M:%S")
        fn_str = dt.datetime.strftime(start_dt, "%Y-%m-%d")
        start_dt = end_dt
        
        querystring['startDateTime'] = start_str
        querystring['endDateTime'] = end_str

        # print(start_str, end_str)
        # commented out for safety - uncomment to call the API
        response = requests.request("GET", url, headers=headers, params=querystring)
        
        if response:
            with open("data/0_raw/weather/weather_{}_21d.csv".format(fn_str), "w") as f:
                f.write(response.text)
                f.close()
                print("weather_{}_21d.csv".format(fn_str))
        
        response = None
        time.sleep(1)


# %%

# %%
### SCRIPT CELL - DON'T RUN IN NOTEBOOK

if __name__ == '__main__':
    # run this step
    run()
