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

    oj = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'oj.csv'))
    # store,brand,week,logmove,feat,price,AGE60,EDUC,ETHNIC,INCOME,HHLARGE,WORKWOM,HVAL150,SSTRDIST,SSTRVOL,CPDIST5,CPWVOL5

    oj['sales'] = oj.logmove.apply(math.exp).apply(int)
    # map week to a date from 2018-01-01 onwards, original data probably starts in 1992-01-10
    oj['date'] = oj.week.apply(lambda x: dt.date(2018,1,1)+dt.timedelta(days=(x-39)*7))

    # filter and sort
    oj = oj[['store', 'brand', 'sales', 'date', 'price', 'AGE60', 'EDUC',
            'ETHNIC', 'INCOME', 'HHLARGE', 'WORKWOM', 'HVAL150', 'SSTRDIST',
            'SSTRVOL', 'CPDIST5', 'CPWVOL5']]

    # rename brand to product
    oj.columns = ['store', 'product', 'sales', 'date', 'price', 'AGE60', 'EDUC',
            'ETHNIC', 'INCOME', 'HHLARGE', 'WORKWOM', 'HVAL150', 'SSTRDIST',
            'SSTRVOL', 'CPDIST5', 'CPWVOL5']

    # ensure / verify grain is sales x store x date
    assert(len(oj)==len(oj.groupby(['store', 'product', 'date'])))

    if from_date_str:
        oj = oj[oj.date >= dt.datetime.strptime(from_date_str, '%Y-%m-%d').date()]
    if to_date_str:
        oj = oj[oj.date <= dt.datetime.strptime(to_date_str, '%Y-%m-%d').date()]

    return oj.reset_index()