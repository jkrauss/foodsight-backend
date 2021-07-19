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
# Serving predictions
# Serving predictions probably means we get the request to predict sales for one or a few days into the future
# The sales-column is to be predicted per day and store. All other columns in the sales-dataset need to be inferred
# the date-dimension is completely known
# for weather-data, we need to retrieve a weather-forecast. Potential missing data-points need to be inferred
# Before we start, we should make sure we have the last update from all sources and the best possible model
# ...the easiest way to get this is to run the complete training-pipeline
#
# Steps
# 0. run complete training-pipeline
# 1. generate (date, store)-tuples in future as per the request
# 2. infer all other columns (except sales) from the sales-dataset, simple approach: linear extrapolation from today
# 3. request weather-forecast for the timeframe as per the prediction-request
# 4. infer all other columns that might be missing from the weather-dataset
# 5. for every additional dataset that might be available infer all columns
# 6. run the prediction-dataset(s) through the transformation-pipeline up until 2_pre_train
# 7. predict sales using the prod-model and write to 6_predict
# 8. inform the requestor that new predictions are readily available
#
# This is a pretty complicated approach, might be possible to do it simpler...
# DONE:
# a. Adpot the whole dataload / transformation pipeline so that
#   DONE: - when weather-history is pulled, also a forecast for the next 14 days is pulled and written on top of the weather-dataset
#   DONE:    - any missing features inferred
#   DONE:     - ensure that every new load of weather-data wipes the forecast and replaces what's possible with real data
#   DONE: - when sales-data is pulled, do steps 1. and 2. above for 7 days
#   DONE:     - the sales-column stays empty so we know what to exclude for train, test, prod
#   SKIPPED: - when other data is pulled, do step 4. respectively
#   DONE: - in 2_prepare_training_data prepare a 4th dataset predict_features, that has 7 "predictive" days prepared as requested
# 
# Now we can add this nb 6_serve_predictions on top of the training-pipeline and run it with every training
# ___Serving any actual requests for predictions is now as simple as filtering the preprocessed result as required___
#
#

import pickle
import pandas as pd
import catboost as cb
import os

#TODO: Generate order_range


# %%
### SCRIPT CELL - DON'T RUN IN NOTEBOOK


def run() :
    # change working directory to where this file lives
    os.chdir(os.path.dirname(os.path.abspath(__file__)))



    # %%
    # load the production model
    model = cb.CatBoostRegressor()
    model.load_model('data/4_train/prod_model.cbm', format='cbm')

    # load prepared prediction-data
    with open('data/4_train/X_predict.pkl', 'rb') as pf:
        X_predict = pickle.load(pf)
    with open('data/4_train/cat_features.pkl', 'rb') as pf:
        cat_features = pickle.load(pf)

    # %%
    predict_pool = cb.Pool(X_predict, cat_features=cat_features)

    # %%
    predictions = model.predict(predict_pool) # array

    # %%
    X_predict['sales_prediction'] = predictions

    # %%
    X_predict[['index', 'store', 'product', 'date', 'sales_prediction']].to_csv('data/6_predict/predictions.csv')

# %%

# %%
### SCRIPT CELL - DON'T RUN IN NOTEBOOK

if __name__ == '__main__':
    # run this step
    run()
