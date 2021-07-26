import pandas as pd


def load_sales(token, store=1, from_date_str=None, to_date_str=None):
    """
    Load sales from a register, using the specified token
    Load data in range from-to. 
    If from is not given loads from the beginning of time.
    If to is not given loads until the most recent data.
    Returns a dataframe with the loaded data
    """
    return pd.DataFrame()