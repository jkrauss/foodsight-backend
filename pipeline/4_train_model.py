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
import pickle
import pandas as pd
import catboost as cb
import os



# %%
### SCRIPT CELL - DON'T RUN IN NOTEBOOK


def run() :
    # change working directory to where this file lives
    os.chdir(os.path.dirname(os.path.abspath(__file__)))



    # %%
    # read data and convert date to datetime
    train = pd.read_csv('data/2_pre_train/train_features.csv')
    train.date = pd.to_datetime(train.date)
    test = pd.read_csv('data/2_pre_train/test_features.csv')
    test.date = pd.to_datetime(test.date)

    prod = pd.read_csv('data/2_pre_train/prod_features.csv')
    prod.date = pd.to_datetime(prod.date)

    predict = pd.read_csv('data/2_pre_train/predict_features.csv')
    predict.date = pd.to_datetime(predict.date)

    # %%
    # mark categorical features for catboost
    g = prod.columns.to_series().groupby(prod.dtypes.apply(str)).groups
    # g.keys() #dict_keys(['bool', 'datetime64[ns]', 'float64', 'int64', 'object'])

    if 'bool' in g.keys():
        if 'object' in g.keys():
            cat_feats = list(g['object']) + list(g['bool'])
        else:
            cat_feats = list(g['bool'])
    else:
        if 'object' in g.keys():
            cat_feats = list(g['object'])
        else:
            cat_feats = []

    # required for catboost: convert categoricals to string and fill none with ''
    for c in cat_feats:
        train[c] = train[c].apply(str).fillna('')
        test[c] = test[c].apply(str).fillna('')
        prod[c] = prod[c].apply(str).fillna('')
        predict[c] = predict[c].apply(str).fillna('')


    # %%
    #train['product']
    cat_feats

# %%

    # %%
    # split train/test frames into dependent and independent variables and stick into catboost's Pool
    X_train, y_train, X_test, y_test = train.drop('sales', axis=1), train['sales'], test.drop('sales', axis=1), test['sales']
    train_pool, test_pool = cb.Pool(X_train, y_train, cat_features = cat_feats), cb.Pool(X_test, y_test, cat_features = cat_feats)

    # same for prod
    X_prod, y_prod = prod.drop('sales', axis=1), prod['sales']
    prod_pool = cb.Pool(X_prod, y_prod, cat_features = cat_feats)

    # write out predict_set for later prediction
    X_predict = predict.drop('sales', axis=1)
    #predict_pool = cb.Pool(X_predict, cat_features = cat_feats) # can't be pickled, maybe cython-problem... whatever
    with open('data/4_train/X_predict.pkl', 'wb') as pf:
        pickle.dump(X_predict, pf)
    with open('data/4_train/cat_features.pkl', 'wb') as pf:
        pickle.dump(cat_feats, pf)

    # a couple parameters for catboost
    params = {'loss_function':'RMSE',
            'eval_metric':'R2',
            'cat_features': cat_feats,
            'early_stopping_rounds': 200,
            'verbose': 50,
    #          'random_seed': SEED
    #          'task_type': 'GPU',
            'iterations': 20000,
            }



    # %%
    # train a model for evaluation
    test_model = cb.CatBoostRegressor(**params)
    test_model.fit(train_pool, eval_set=test_pool
    #, plot=True
    )

    # %%
    # TODO: generate more evaluation metrics

    # print R2 score that was used for training evaluation
    test_model.score(test_pool)

    # %%
    # save test-model for later inspection
    test_model.save_model('data/4_train/test_model.cbm', format='cbm', pool=train_pool)

    # %%
    # train a model for production

    # set number of iterations to the best found number from test
    params['iterations'] = test_model.best_iteration_
    prod_model = cb.CatBoostRegressor(**params)
    prod_model.fit(prod_pool)

    # %%
    # THIS IS A VANITY METRIC! The model has seen the test-data, so this can't be taken seriously...
    prod_model.score(test_pool), prod_model.score(train_pool)

    # %%
    # save prod-model for production
    prod_model.save_model('data/4_train/prod_model.cbm', format='cbm', pool=prod_pool)

# %%

# %%
### SCRIPT CELL - DON'T RUN IN NOTEBOOK

if __name__ == '__main__':
    # run this step
    run()
