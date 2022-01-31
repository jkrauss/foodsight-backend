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
import duckdb as dd
import json


config = {'base': 
    {'register_plugin': 'plugins.ready2order.ready2order'
    , 'register_plugin_name': 'ready2order'
    , 'country': 'DE'
    , 'state': 'HE'
    , 'city': 'Wiesbaden'
    , 'customer_id': 0
    , 'pipeline_path': '/Users/jonni/dev/foodsight-backend/pipeline'
    , 'returns_current': 250
    , 'sales_price_cost_share': 0.3
    }}


# %%
### SCRIPT CELL - DON'T RUN IN NOTEBOOK
# TODO: introduce and handle product_number as id correctly through the pipeline

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
    predictions_per_store = {}
    for store in X_predict.store.unique():
        predictions_per_store[store] = X_predict.loc[X_predict.store==store, ['product', 'date', 'sales_prediction']].pivot(index=['product'], columns='date', values='sales_prediction')

    # %%
    prod = pd.read_csv(f'data/customer/{config["base"]["customer_id"]}/2_pre_train/prod_features.csv')
    prod.date = pd.to_datetime(prod.date)

    last_seven = prod.sort_values('date', ascending=True).date.unique()[-7:]
    prod = prod[prod.date.isin(last_seven)]
    
    last_week_per_store = {}
    for store in prod.store.unique():
        last_week_per_store[store] = prod.loc[prod.store==store, ['product', 'date', 'sales']].pivot(index=['product'], columns='date', values='sales')
        last_week_per_store[store] = last_week_per_store[store].fillna(0)

    # TODO:
    # Learning: The curent implementation does only predict conditional... 
    # "if there's sales on that date for that product it's going to be XYZ"
    # This is far off for products that have often 0 sales on a date
    last_week_per_store[1]

    # %%
    # TODO: From here onwards I pretty much ignore the fact that there can be more than one store

    diff = last_week_per_store[1].copy(deep=True)
    diff.columns = predictions_per_store[1].columns# - last_week_per_store[1]
    diff = predictions_per_store[1] - diff

    diff = diff.dropna() # This means we don't predict products that haven't sold last week!
    #diff

    # %%
    # calculate the maximum order quantity as the forecast plus the maximum difference that the forecast had to last weeks actual

    add_this = diff.copy(deep=True)
    # value_when_true if condition else value_when_false
    for c in add_this.columns:
        add_this[c] = add_this[c].apply(lambda x: 0 if x > 0 else x)
    #max_order = (diff / predictions_per_store[1]).dropna()
    add_this = add_this.T.min()
    add_this.name = 'add_this'
    #add_this

    max_order = pd.merge(predictions_per_store[1], add_this, on='product')
    for c in max_order.columns:
        max_order[c] -= max_order.add_this

    max_order = max_order.drop('add_this', axis=1)
    #max_order

    # %%
    # calculate the minimum order quantity as the forecast minus the maximum positive difference that the forecast had to last weeks actual

    add_this = diff.copy(deep=True)
    # value_when_true if condition else value_when_false
    for c in add_this.columns:
        add_this[c] = add_this[c].apply(lambda x: 0 if x < 0 else x)
    #max_order = (diff / predictions_per_store[1]).dropna()
    add_this = add_this.T.max()
    add_this.name = 'add_this'
    #add_this

    min_order = pd.merge(predictions_per_store[1], add_this, on='product')
    for c in min_order.columns:
        min_order[c] -= min_order.add_this
        min_order[c] = min_order[c].apply(lambda x: 0 if x < 0 else x)

    min_order = min_order.drop('add_this', axis=1)
    #min_order

    # %%
    step = (max_order - min_order)/4
    XS = min_order
    S = XS + step
    M = S + step
    L = M + step
    XL = L + step
    #XL - max_order

    # %%
    order_sets = {
        'XS': XS.round(),
        'S': S.round(),
        'M': M.round(),
        'L': L.round(),
        'XL': XL.round()
    }


    # %%
    for S in order_sets:
        # above we have asserted that prod only contains last seven days: prod = prod[prod.date.isin(last_seven)]
        # TODO: FIXME: Here I assume that I will have a field 'item_product_pricePerUnit' - which is only given with ready2order
        prices = prod.groupby(['product', 'item_product_pricePerUnit']).count()['index'].reset_index()[['product', 'item_product_pricePerUnit']]

        act = last_week_per_store[1].copy(deep=True)
        act.columns = order_sets[S].columns
        diff = (order_sets[S] - act).T # how much more is the forecast than the act?
        plus = 0
        minus = 0
        for val in diff['Bier']:
            if val > 0:
                plus += val
            else:
                minus += val

        # calculate weekly revenue from last week actuals
        act_sum = act.T.sum().reset_index()
        act_sum.columns = ['product', 'act_sum']
        act_sum = pd.merge(act_sum, prices[['item_product_pricePerUnit', 'product']], on='product')
        act_sum['revenue'] = act_sum.item_product_pricePerUnit * act_sum.act_sum
        weekly_revenue = act_sum.revenue.sum()
        weekly_revenue

        prices['above'] = 0
        prices['below'] = 0

        for c in diff.columns:
            row = diff.T.loc[c,:]
            prices.loc[prices['product']==c,'above'] = row[row>0].sum()
            prices.loc[prices['product']==c,'below'] = row[row<0].sum()

        prices.above *= prices.item_product_pricePerUnit
        prices.below *= prices.item_product_pricePerUnit

        prices.below *= -1.0

        donut_data = prices.sum()[['above', 'below']]#.to_dict()

        # calc given data (for 7 days) for a month
        donut_data *= 4.333
        donut_data['returns_current'] = config['base']['returns_current']*30.417
        donut_data['returns_savings'] = donut_data['returns_current'] - donut_data['above']
        # rename above to 'returns_remaining
        donut_data['returns_remaining'] = donut_data['above']

        donut_data['profits_current'] = weekly_revenue*4.333
        donut_data['profits_lost'] = donut_data['below']#*4.333
        donut_data['profits_remaining'] = donut_data['profits_current'] - donut_data['profits_lost']

        donut_data.drop(['above', 'below'], axis=0, inplace=True)

        # calculate return delivery fields as cost only
        donut_data[['returns_current', 'returns_savings', 'returns_remaining']] *= config['base']['sales_price_cost_share']
        # calculate mohtly profits as profits only
        donut_data[['profits_current', 'profits_lost', 'profits_remaining']] *= (1- config['base']['sales_price_cost_share'])

        order_sets[S].columns = [str(d)[:10] for d in order_sets[S].columns]
        return_dict = {
            'name': S,
            'donut_data': donut_data.to_dict(),
            'products': list(order_sets[S].index),
            'order_quantity': order_sets[S].to_dict()
        }
        order_sets[S] = return_dict

    # %%
    # ['name', 'donut_data', 'products', 'order_quantity']
    # order_sets['L']['products'] #['donut_data']

# %%

# %%
fname = f'data/customer/{config["base"]["customer_id"]}/6_predict/predictions.json'
with open(fname, 'w') as fp:
    json.dump(order_sets, fp)

# %%
### SCRIPT CELL - DON'T RUN IN NOTEBOOK

# if __name__ == '__main__':
    # run this step
#     run()
