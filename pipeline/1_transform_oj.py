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
import pandas as pd
import math
import datetime as dt
import os



# %%
### SCRIPT CELL - DON'T RUN IN NOTEBOOK


def run() :
    # change working directory to where this file lives
    os.chdir(os.path.dirname(os.path.abspath(__file__)))



    # %%
    # TODO: Generate features like same day last year, week, month, last 7 days

    # %%
    oj = pd.read_csv('data/0_raw/oj.csv')

    # %%
    # logmove contains the log of the number of units sold
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

    # %%
    # ensure / verify grain is sales x store x date
    assert(len(oj)==len(oj.groupby(['store', 'product', 'date'])))

    # %% tags=[]
    # generate a 7-days prediction-"template" and infer/fill all columns except 'sales'
    # 1. generate (date, store, date)-tuples in future as per the request
    # 2. infer all other columns (except sales) from the sales-dataset, simple approach: average last 3 days for numericals, "vote" of three for categoricals

    # we mark the prediction-data with sales==None - therefore all sales before must be not None
    oj.loc[:,'sales'].fillna(0)

    # generate (date, store, date)-tuples in future as per the request
    products = oj['product'].unique()
    stores = oj['store'].unique()
    # next seven days from the last date in oj
    dates = [pd.to_datetime(oj.date).max() + dt.timedelta(days=(i+1)) for i in range(7)]

    # groups we can access to retrieve last three and average per tuple
    grp = oj.sort_values('date', ascending=True).groupby(['store', 'product'])

    # these columns need to be inferred from the last 3 values
    infer_columns = [x for x in list(oj.columns) if x not in ['store', 'product', 'sales', 'date']]

    # dict-like if the cols are numeric
    is_num = oj[infer_columns].dtypes.apply(lambda x: pd.api.types.is_numeric_dtype(x))#['INCOME']

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
                        row.append(grp.get_group((s, p))[-3:][c].mode()[0])
                data.append(row)

    future = pd.DataFrame(data=data, columns=['store', 'product', 'sales', 'date']+infer_columns)



    # %%
    #concat historic and future sales
    assert (future.columns == oj.columns).all()
    oj = pd.concat([oj, future])


    # %%
    oj.reset_index().to_csv('data/1_trans/current_sales_history.csv', index=False)

# %%

# %%
### SCRIPT CELL - DON'T RUN IN NOTEBOOK

if __name__ == '__main__':
    # run this step
    run()
