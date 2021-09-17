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

config = {'base': 
    {'register_plugin': 'plugins.manual.manual'
    , 'register_plugin_name': 'manueller Import'
    , 'country': 'DE'
    , 'state': 'HE'
    , 'city': 'Wiesbaden'
    , 'customer_id': 0
    , 'pipeline_path': '/Users/jonni/dev/foodsight-backend/pipeline'
    }}


# %%
### SCRIPT CELL - DON'T RUN IN NOTEBOOK

# import util
# config = util.load_config()

def run(config_in) :
    global config
    config = config_in
    # change working directory to where this file lives
    os.chdir(config['base']['pipeline_path'])



    # %%
    # load the production model
    model = cb.CatBoostRegressor()
    model.load_model(f'data/customer/{config["base"]["customer_id"]}/4_train/prod_model.cbm', format='cbm')

    # load prepared prediction-data
    with open(f'data/customer/{config["base"]["customer_id"]}/4_train/X_predict.pkl', 'rb') as pf:
        X_predict = pickle.load(pf)
    with open(f'data/customer/{config["base"]["customer_id"]}/4_train/cat_features.pkl', 'rb') as pf:
        cat_features = pickle.load(pf)

    # %%
    predict_pool = cb.Pool(X_predict, cat_features=cat_features)

    # %%
    predictions = model.predict(predict_pool) # array

    # %%
    X_predict['sales_prediction'] = predictions

    # %%
    # TODO: introduce and handle product_number as id correctly through the pipeline
    result = X_predict[['store', 'date', 'product', 'sales_prediction']]

    # ensure we only return numbers for next seven days and filter/format a bit
    dates = result.date.unique()
    dates.sort()

    result = result[result.date.isin(dates[:7])].reset_index(drop=True).reset_index()
    # ATTENTION! Is dependent on the order of the filter above result = X_predict[[...
    result.columns=['id', 'store', 'date', 'product', 'forecast']


    # %%
    # TODO: do a proper calculation of order-range instead of this 
    result['order_from'] = (result.forecast*0.85)
    result['order_to'] = (result.forecast*1.15)

    # %%
    # build 3 frames: tomorrow, day_after, seven_days
    tomorrow = result[result.date==dates[0]][['id', 'store', 'product', 'forecast', 'order_from', 'order_to']]
    day_after = result[result.date==dates[1]][['id', 'store', 'product', 'forecast', 'order_from', 'order_to']]
    seven_days = result[['store', 'product', 'forecast', 'order_from', 'order_to']].groupby(['store', 'product']).sum().reset_index()
    
    # needs to be changed as soon as we have proper product-numbers!
    seven_days.reset_index(inplace=True)
    seven_days.columns = ['id', 'store', 'product', 'forecast', 'order_from', 'order_to']
    
    # needs to be changed as soon as we have proper product-numbers!
    day_after.reset_index(inplace=True, drop=True)
    day_after.reset_index(inplace=True)
    day_after = day_after[['index', 'store', 'product', 'forecast', 'order_from', 'order_to']]
    day_after.columns = ['id', 'store', 'product', 'forecast', 'order_from', 'order_to']

    # %%
    # create ..._order_range text-fields
    tomorrow['tomorrow_order_range'] = tomorrow.order_from.apply(round).apply(str) + ' - ' + tomorrow.order_to.apply(round).apply(str)
    day_after['day_after_order_range'] = day_after.order_from.apply(round).apply(str) + ' - ' + day_after.order_to.apply(round).apply(str)
    seven_days['next7_order_range'] = seven_days.order_from.apply(round).apply(str) + ' - ' + seven_days.order_to.apply(round).apply(str)


    # %%
    # prepare for merge / rename cols to target-names
    for df in [tomorrow, day_after, seven_days]:
        df.forecast = df.forecast.apply(round)
    tomorrow = tomorrow[['id', 'store', 'product', 'forecast', 'tomorrow_order_range']]
    tomorrow.columns = ['id', 'store', 'product', 'tomorrow_order_qty', 'tomorrow_order_range']
    day_after = day_after[['id', 'store', 'product', 'forecast', 'day_after_order_range']]
    day_after.columns = ['id', 'store', 'product', 'day_after_order_qty', 'day_after_order_range']
    seven_days = seven_days[['id', 'store', 'product', 'forecast', 'next7_order_range']]
    seven_days.columns = ['id', 'store', 'product', 'next7_order_qty', 'next7_order_range']

    tomorrow

    # %%
    keys = ['id', 'store', 'product']
    result = pd.merge(pd.merge(tomorrow, day_after, left_on=keys, right_on=keys)
        , seven_days, left_on=keys, right_on=keys)
    result

    # %%
    result.to_csv(f'data/customer/{config["base"]["customer_id"]}/6_predict/predictions.csv', index=False)

# %%

# %%
### SCRIPT CELL - DON'T RUN IN NOTEBOOK

# if __name__ == '__main__':
    # run this step
#     run()
