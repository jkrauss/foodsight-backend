# ---
# jupyter:
#   jupytext:
#     formats: py:percent,ipynb
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.12.0
#   kernelspec:
#     display_name: 'Python 3.8.10 64-bit (''.venv'': venv)'
#     name: python3
# ---

# %%

# %%
import datetime as dt
import requests
import time
import pandas as pd

import os


config = {'base': 
    {'register_plugin': 'plugins.ready2order.ready2order'
    , 'register_plugin_name': 'ready2order'
    , 'country': 'DE'
    , 'state': 'HE'
    , 'city': 'Wiesbaden'
    , 'customer_id': 0
    , 'pipeline_path': '/Users/jonni/dev/foodsight-backend/pipeline'
    }}


# %%
### SCRIPT CELL - DON'T RUN IN NOTEBOOK
#import util
#config = util.load_config()

def run(config_in) :
    global config
    config = config_in
    # change working directory to where this file lives
    os.chdir(config['base']['pipeline_path'])



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
        'x-rapidapi-key': os.environ.get('RAPID_API_KEY'),
        'x-rapidapi-host': "visual-crossing-weather.p.rapidapi.com"
        }

    # %%
    # ATTENTION! There's a limit of 500 requests per MONTH on the API - use very carefully!
    # There's also a limit of 500 lines per API call - this gives a max of 21 days * 24 hours (21 is too much)
    response = requests.request("GET", url, headers=headers, params=querystring)

    fn_str = str(dt.date.today())
    if response:
        with open(f'data/customer/{config["base"]["customer_id"]}/0_raw/weather_forecast/forecast.csv', "w") as f:
            f.write(response.text)
            f.close()
            print("forecast.csv from {}".format(fn_str))


# %%

# %%
### SCRIPT CELL - DON'T RUN IN NOTEBOOK

# if __name__ == '__main__':
    # run this step
#     run()

# %%
