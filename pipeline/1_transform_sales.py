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
import pandas as pd
import math
import datetime as dt
import os
import glob

import numpy as np
import statistics

import util
config = util.load_config()

# %%
### SCRIPT CELL - DON'T RUN IN NOTEBOOK


def run() :
    # change working directory to where this file lives
    os.chdir(config['base']['pipeline_path'])



    # %%
    # TODO: Generate features like same day last year, week, month, last 7 days

    # %%
    # list all files that are to be concatenated
    flist = list()
    for filepath in glob.iglob('data/0_raw/sales/*.csv'):
        flist.append(filepath)

    # this sorts the original list in place
    flist.sort()

    full_df = pd.DataFrame()
    for f in flist:
        # can be empty csv-files or files with one space
        if os.path.getsize(f) > 1:
            df = pd.read_csv(f)
            if len(full_df)== 0:
                full_df = df
            elif list(df.columns)==list(full_df.columns):
                full_df = pd.concat([full_df, df])


    # %%
    # don't aggregate the index..
    full_df.drop('index', axis=1, inplace=True)
    
    # dict-like if the cols are numeric
    is_num = full_df.dtypes.apply(lambda x: pd.api.types.is_numeric_dtype(x))

    # determine most frequent value to use as aggregate function for categoricals
    def most_frequent(in_list):
        lst = list(in_list)
        return max(set(lst), key=lst.count)

    # numericals : mean, categoricals: most frequent value, sales : summarize
    def v(c):
        if c == 'sales':
            return np.sum
        elif is_num[c]:
            return np.mean
        else:
            return most_frequent
    
    # assign an appropriate aggregate function to each column that is not in the groupby
    agg_dict = {c : v(c) for c in [c for c in full_df.columns if c not in ['store', 'product', 'date']]}

    # group, aggregate and reset index
    df = full_df.groupby(['store', 'product', 'date']).agg(agg_dict).reset_index()


    # %%
    # ensure / verify grain is sales x store x date
    assert(len(df)==len(df.groupby(['store', 'product', 'date'])))

    # %% tags=[]
    # generate a 7-days prediction-"template" and infer/fill all columns except 'sales'
    # 1. generate (date, store, date)-tuples in future as per the request
    # 2. infer all other columns (except sales) from the sales-dataset, simple approach: average last 3 days for numericals, "vote" of three for categoricals

    # we mark the prediction-data with sales==None - therefore all sales before must be not None
    df.loc[:,'sales'].fillna(0, inplace=True)

    # generate (date, store, date)-tuples in future as per the request
    products = df['product'].unique()
    stores = df['store'].unique()
    # next seven days from the last date in oj
    dates = [pd.to_datetime(df.date).max().date() + dt.timedelta(days=(i+1)) for i in range(7)]

    # groups we can access to retrieve last three and average per tuple
    grp = df.sort_values('date', ascending=True).groupby(['store', 'product'])

    # these columns need to be inferred from the last 3 values
    infer_columns = [x for x in list(df.columns) if x not in ['store', 'product', 'sales', 'date']]

    data = list()
    for d in dates:
        for s in stores:
            for p in products:
                # store product, sales, date
                row = [s,p,None,d]
                for c in infer_columns:
                    if is_num[c]: # mean of last 3
                        row.append(grp.get_group((s, p))[-3:][c].mean())
                    else: # most frequent value of last 3
                        mode_list = grp.get_group((s, p))[-3:][c].mode()
                        if len(mode_list) > 0:
                            row.append(mode_list[0])
                        else:
                            row.append(None)
                data.append(row)

    future = pd.DataFrame(data=data, columns=['store', 'product', 'sales', 'date']+infer_columns)



    # %%
    #concat historic and future sales
    df = df[['store', 'product', 'sales', 'date']+infer_columns]
    df = pd.concat([df, future])


    # %%
    df.reset_index().to_csv('data/1_trans/current_sales_history.csv', index=False)

# %%
### SCRIPT CELL - DON'T RUN IN NOTEBOOK

if __name__ == '__main__':
    # run this step
    run()

# %%
