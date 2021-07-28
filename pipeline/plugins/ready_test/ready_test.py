from numpy import concatenate
import pandas as pd
from pandas.io.json import json_normalize #package for flattening json in pandas df
import math
import datetime as dt
import os

def load_sales(token, store=1, from_date_str=None, to_date_str=None):
    """
    Load sales from a register, using the specified token
    Load data in range from-to. 
    If from is not given loads from the beginning of time.
    If to is not given loads until the most recent data.
    Returns a dataframe with the loaded data
    """

    oj = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'current_sales_history.csv'))
    oj.date = pd.to_datetime(oj.date).apply(lambda x: x.date())

    # ensure / verify grain is sales x store x date
    assert(len(oj)==len(oj.groupby(['store', 'product', 'date'])))

    if from_date_str:
        oj = oj[oj.date >= dt.datetime.strptime(from_date_str, '%Y-%m-%d').date()]
    if to_date_str:
        oj = oj[oj.date <= dt.datetime.strptime(to_date_str, '%Y-%m-%d').date()]

    return oj.reset_index()