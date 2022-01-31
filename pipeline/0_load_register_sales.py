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
import datetime as dt
import pandas as pd
import numpy as np
import sys, os
import pathlib

import importlib


config = {'base': 
    {'register_plugin': 'plugins.ready2order.ready2order'
    , 'register_plugin_name': 'ready2order'
    , 'country': 'DE'
    , 'state': 'HE'
    , 'city': 'Wiesbaden'
    , 'customer_id': 0
    , 'pipeline_path': '/Users/jonni/dev/foodsight-backend/pipeline'
    }}

# import util
# load customer specific config
#config = util.load_config()


# %%
### SCRIPT CELL - DON'T RUN IN NOTEBOOK


def run(config_in) :
    global config
    config = config_in
    # change working directory to where this file lives
    os.chdir(config['base']['pipeline_path'])

# %%
    
    CUSTOMER_TOKEN = os.environ.get('CUSTOMER_TOKEN')

    # load the register-plugin of the customer
    plug = importlib.import_module(config['base']['register_plugin'])
    #plug = importlib.import_module('pipeline.plugins.ready2order.ready2order')

    # %%
    # import imp
    # imp.reload(plug)

    start_date = dt.date(2018,1,1)
    str(start_date)
    while start_date < dt.date.today():
        # determine 4 weeks batch then increment
        end_date = start_date + dt.timedelta(weeks=4)
        start_str = str(start_date)
        end_str = str(end_date)
        csv_name = f'data/customer/{config["base"]["customer_id"]}/0_raw/sales/sales_{start_str}_{end_str}.csv'

        # if historic data exists don't load, but always reload current batch - 3 days grace period for a hanging pipeline
        if not ( end_date + dt.timedelta(days=3) < dt.date.today() and os.path.isfile(csv_name) ):
            print(f'loading {csv_name}...')
            sales = plug.load_sales(CUSTOMER_TOKEN, from_date_str=start_str, to_date_str=end_str)
            sales.to_csv(csv_name, index=False)
        
        # increment
        start_date = end_date+dt.timedelta(days=1)


# %%
### SCRIPT CELL - DON'T RUN IN NOTEBOOK

# if __name__ == '__main__':
    # run this step
#     run()

# %%
