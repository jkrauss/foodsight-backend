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
# inputs are sales, weather and other data-files. Each file has a date-column, the sales-file has the target-column and it's named 'sales'
# # ? Doe we use featuretools before aggregating per date or afterwards or both ?

import pandas as pd
import glob
import featuretools as ft
import datetime as dt
import pickle
import os

import util
config = util.load_config()

# %%
### SCRIPT CELL - DON'T RUN IN NOTEBOOK


def run() :
    # change working directory to where this file lives
    os.chdir(config['base']['pipeline_path'])



    # %%
    # TODO: assert constraints, like all frames contain date, sales-file contains sales and is numeric, ...

# %% [markdown]
# # read data 

    # %%
    salespath = 'data/1_trans/current_sales_history.csv'
    datepath = 'data/1_trans/date_dimension.csv'

    # %%
    # contains our target column 'sales' : initialize our dataset
    sales = pd.read_csv(salespath)
    sales.date = pd.to_datetime(sales.date)

    # contains the time-dimension
    days = pd.read_csv(datepath)
    days.date = pd.to_datetime(days.date)


    # %%
    # list all files that are to be merged
    flist = list()
    for filepath in glob.iglob('data/1_trans/*.csv'):
        if filepath != salespath and filepath != datepath:
            flist.append(filepath)
            print(filepath)


    # read all data into a dict of df's
    prod_data = {'sales':sales, 'days':days}
    for f in flist:
        df = pd.read_csv(f)
        df.date = pd.to_datetime(df.date)
        # name entities as their filenames without '.csv' and path
        entity_name = f.split('/')[-1].rsplit('.')[0]
        prod_data[entity_name] = df


# %%

    # trim time- and other dimensions to the timespan present in sales
    start, end = sales.date.min(), sales.date.max()

    for el in prod_data:
        prod_data[el] = prod_data[el][(prod_data[el].date >= start)&(prod_data[el].date <= end)]

    # %%
    prod_data.keys()

    # %%
    # prod_data['sales'].date.max(), prod_data['days'].date.max(), prod_data['weather'].date.max()

# %% [markdown]
# # cut train, test and prod datasets

    # %%
    # pd.to_datetime((prod_data['sales'][prod_data['sales'].sales.isna()].date)).min()

    # %%
    # First separate the prediction-set from the data for training
    pred_cutoff = pd.to_datetime((prod_data['sales'][prod_data['sales'].sales.isna()].date)).min()

    # cut data into respective dicts train_data and test_data
    predict_data =  {}
    for el in prod_data:
        df = prod_data[el]
        # all data up until cutoff_date into predict_data
        predict_data[el] = df[df.date>=pred_cutoff]
        # remove from all training-sets
        prod_data[el] = df.drop(df[df.date>=pred_cutoff].index, axis=0)

    # assert no prediction-data is left
    for el in prod_data:
        df = prod_data[el]
        #print(df.date.max())
        assert df.date.max() < pred_cutoff, '{}-data must not contain elements from the prediction-set'.format(el)

    # %%
    # We intend to train a model on a training set and measure accuracy/quality using a test-set
    # , that the model has not seen during training
    # The usecase lends well to split the data based on time
    # The first 75% of time goes into the training-set, the last 25% into the test-set
    # After validation, we want to train the model of course on all available data,
    # therefore the 3rd set 'prod' contains all data

    # calculate train, test, prod timespans and cutoff-date
    timespan = (pred_cutoff - sales.date.min()).days
    train_span = int(timespan*0.75)
    test_span = timespan - train_span
    cutoff_date = start+dt.timedelta(days=train_span)

    timespan, train_span, test_span, start, pred_cutoff, cutoff_date

    # %%
    # cut data into respective dicts train_data and test_data
    train_data, test_data = {}, {}
    for el in prod_data:
        # all data up until cutoff_date into train
        train = prod_data[el][prod_data[el].date<=cutoff_date]
        train_data[el] = train
        # all data after cutoff_date into test
        test = prod_data[el][prod_data[el].date>cutoff_date]
        test_data[el] = test

    train_data.keys(), test_data.keys()    

    # %%
    # assert we have sufficient data in each set and time-cuts worked out correctly
    for el in train_data:
        #print(el, len(train_data[el]), train_data[el].date.max())
        assert len(train_data[el]) >= 10, 'train data of {} should have at least 10 examples'.format(el, cutoff_date)
        assert train_data[el].date.max() <= cutoff_date, 'train data of {} should not contain dates after cutoff_date {}'.format(el, cutoff_date)

    for el in test_data:
        #print(el, len(test_data[el]), test_data[el].date.min())
        assert len(test_data[el]) >= 10, 'test data of {} should have at least 10 examples'.format(el, cutoff_date)
        assert test_data[el].date.min() > cutoff_date, 'test data of {} should not contain dates before/at cutoff_date {}'.format(el, cutoff_date)


# %% [markdown]
# # generate entity-sets for featuretools

    # %%
    # initiate/fill 4 entity-sets with mandatory entities days and sales
    prod_entities = {
        'days' : (prod_data['days'], 'date'),
        'sales': (prod_data['sales'], 'index', 'date')
    }
    train_entities = {
        'days' : (train_data['days'], 'date'),
        'sales': (train_data['sales'], 'index', 'date')
    }
    test_entities = {
        'days' : (test_data['days'], 'date'),
        'sales': (test_data['sales'], 'index', 'date')
    }
    predict_entities = {
        'days' : (predict_data['days'], 'date'),
        'sales': (predict_data['sales'], 'index', 'date')
    }

    # relations are the same for prod, train and test
    relations = [
        ('days', 'date', 'sales', 'date')
    ]

    # add all additional entities to prod, train, test, prediction entity-sets
    for el in prod_data:
        if el not in ['days', 'sales']:
            prod_entities[el] = (prod_data[el], 'index', 'date')
            relations.append(('days', 'date', el, 'date'))

    for el in train_data:
        if el not in ['days', 'sales']:
            train_entities[el] = (train_data[el], 'index', 'date')

    for el in test_data:
        if el not in ['days', 'sales']:
            test_entities[el] = (test_data[el], 'index', 'date')

    for el in predict_data:
        if el not in ['days', 'sales']:
            predict_entities[el] = (predict_data[el], 'index', 'date')

# %% [markdown]
# # generate features

    # %%
    # These primitives are to be used in feature synthesis
    trans_prim = ["day", "week", "month", "weekday", "haversine", "num_words", "num_characters"]
    where_prim = ["count"]
    agg_prim =  ["sum", "std", "max", "skew", "min", "mean", "count", "percent_true", "num_unique", "mode"]

    # TODO: Ensure to produce "feature-leakage" on the date-dimension e.g. that the model knows, that a specific holiday, weekend, school-vacation etc... lies ahead
    # TODO: Double-check that we don't have a problem because of the different sizes of train, test, prod, predict
    # e.g. does agg_prim 'count' only count per target-row (no problem)? or does it count the whole dataset (problem)? 



    # %%
    prod_features, prod_feature_defs = ft.dfs(entities=prod_entities, relationships=relations, target_entity='sales', n_jobs=1, agg_primitives=agg_prim, trans_primitives=trans_prim, where_primitives=where_prim)

    # %%
    train_features, train_feature_defs = ft.dfs(entities=train_entities, relationships=relations, target_entity='sales', n_jobs=1, agg_primitives=agg_prim, trans_primitives=trans_prim, where_primitives=where_prim)

    # %%
    test_features, test_feature_defs = ft.dfs(entities=test_entities, relationships=relations, target_entity='sales', n_jobs=1, agg_primitives=agg_prim, trans_primitives=trans_prim, where_primitives=where_prim)

    # %%
    predict_features, predict_feature_defs = ft.dfs(entities=predict_entities, relationships=relations, target_entity='sales', n_jobs=1, agg_primitives=agg_prim, trans_primitives=trans_prim, where_primitives=where_prim)

    # %%
    assert prod_feature_defs==train_feature_defs==test_feature_defs==predict_feature_defs, 'prod train and test should have the same feature definitions'

    # %%
    type(prod_features), type(prod_feature_defs)

    # %%
    # predict_features

    # %%
    # Write datasets and feature definitions to 2_pre_train folder

    # doesn't work? nevermind... not needed
    # for df in [prod_features, train_features, test_features]:
    #     df = df.reset_index(drop=True)


    prod_features.to_csv('data/2_pre_train/prod_features.csv')
    train_features.to_csv('data/2_pre_train/train_features.csv')
    test_features.to_csv('data/2_pre_train/test_features.csv')
    predict_features.to_csv('data/2_pre_train/predict_features.csv')

    with open('data/2_pre_train/feature_def_list.pkl', 'wb') as f:
        pickle.dump(prod_feature_defs, f)


    # %%
    len(prod_feature_defs)

# %%

# %%
### SCRIPT CELL - DON'T RUN IN NOTEBOOK

if __name__ == '__main__':
    # run this step
    run()
