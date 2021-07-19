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

# %%
import datetime as dt
import requests
import time
import pandas as pd

import os


# %%
### SCRIPT CELL - DON'T RUN IN NOTEBOOK


def run() :
    # change working directory to where this file lives
    os.chdir(os.path.dirname(os.path.abspath(__file__)))



    # %%
    url = "https://visual-crossing-weather.p.rapidapi.com/forecast"

    querystring = {
        "aggregateHours":"1"
        ,"location":"50.0826,8.2493"
        ,"unitGroup":"metric"
        ,"contentType":"csv"
        ,"shortColumnNames":"0"
        }

    headers = {
        'x-rapidapi-key': "0775822d7dmshcc59ba9c3899f48p1c5f41jsn6c9e54ea8866",
        'x-rapidapi-host': "visual-crossing-weather.p.rapidapi.com"
        }

    # %%
    # ATTENTION! There's a limit of 500 requests per MONTH on the API - use very carefully!
    # There's also a limit of 500 lines per API call - this gives a max of 21 days * 24 hours (21 is too much)
    response = requests.request("GET", url, headers=headers, params=querystring)

    fn_str = str(dt.date.today())
    if response:
        with open("data/0_raw/weather_forecast/forecast.csv", "w") as f:
            f.write(response.text)
            f.close()
            print("forecast.csv from {}".format(fn_str))


# %%

# %%
### SCRIPT CELL - DON'T RUN IN NOTEBOOK

if __name__ == '__main__':
    # run this step
    run()
