from numpy import concatenate
import pandas as pd
from pandas.io.json import json_normalize #package for flattening json in pandas df
import requests
import toml
import pathlib
import time

company_url = "https://api.ready2order.com/v1/company"
invoice_url = "https://api.ready2order.com/v1/document/invoice"
product_url = "https://api.ready2order.com/v1/products"

product_querystring = {
    'includeProductGroup' : True,
    'includeProductVariations' : True,
    'includeProductIngredients' : True,
    'limit' : 1000,
    'page' : 1
}

invoice_querystring = {
        'items' : True,
        'dateFrom' : '',
        'dateTo' : '',
        'offset' : 0,
        'limit' : 100, # max number of rows to retrieve, default is 25
        'query' : 'RG' # type."billType_symbol": "RG" is what I actually want
}

def load_sales(token, store=1, from_date_str=None, to_date_str=None):
    """
    Load sales from a register, using the specified token
    Load data in range from-to. 
    If from is not given loads from the beginning of time.
    If to is not given loads until the most recent data.
    Returns a dataframe with the loaded data
    """
    headers = {
        'Authorization' : token
    }

    invoice_querystring['dateFrom'] = from_date_str
    invoice_querystring['dateTo'] = to_date_str

    more = True
    return_df = None
    while(more):
        response = requests.request("GET", invoice_url, headers=headers, params=invoice_querystring)
        time.sleep(1) # ensure rate limit of 60 requests per minute

        if response:
            sales = response.json()
        else:
            sales = {'invoices': []}

        n_invoices = len(sales['invoices'])
        if n_invoices==0:
            more=False
            df=pd.DataFrame()
        else:
            print(f"retrieved {n_invoices} invoices from ready2order")
            # if we received more data, we want to do another round next time until we receive no more data
            invoice_querystring['offset'] += len(sales['invoices'])

            # extract invoices and invoice-items into flat tables and join
            invoices = pd.json_normalize(sales['invoices'], errors='ignore')
            print(f"{len(invoices)} invoices")
            items = pd.json_normalize(sales['invoices'], record_path=['items'], errors='ignore')
            print(f"{len(items)} items")

            df = pd.merge(invoices, items, how='inner', left_on='invoice_id', right_on='invoice_id')
            print(f"{len(df)} new rows")
            # load whitelist and exclude all other fields
            whitelist = toml.load(pathlib.Path(__file__).parent.resolve()/'fields.toml')['whitelist']
            df = df[whitelist]

            # rename / identify important fields date, sales, product, store
            name_dict = {
                'item_timestamp' : 'date',
                'item_qty' : 'sales',
                'item_product_name' : 'product',
                'item_id' : 'index'
            }
            df.rename(columns=name_dict, inplace=True)
            df['store'] = store
            df.loc[:,'date'] = pd.to_datetime(df['date']).apply(lambda x: x.date())

            # set sales to 0 for deleted invoices
            df.loc[~df['invoice_deleted_at'].isna(), 'sales'] = 0
            # encode categoricals as string so they are being handled correctly in later pipeline
            for col in ['customerCategory_id', 'tableArea_id', 'paymentMethod_id_x']:
                df.loc[:,col] = df[col].apply(lambda x : x if x is None else f"cat_{str(x)}")
        
        # while more we append more rows to the final dataframe that we want to return
        if return_df is None:
            return_df = df
        else:
            if more:
                return_df = pd.concat([return_df, df], axis=0)
            #return_df = df
            print(f"{len(return_df)} return rows")
    if len(return_df) > 0:
        assert len(return_df.index.unique()) == len(return_df), "The number of rows should equal the number of unique indices"
    return return_df