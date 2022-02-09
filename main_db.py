#import sqlite3 as sql
import pandas as pd
from pydantic import BaseModel
from typing import Optional

import pathlib
import shutil

import main_auth as auth

import json

import dotenv
from cachetools import cached, TTLCache
dotenv.load_dotenv()
# Naming convention: create_..., read_..., update_..., delete_...

import spaces
class User(BaseModel):
    username: str
    full_name: Optional[str] = None
    disabled: Optional[bool] = None

class UserSettings(BaseModel):
    returns_current: Optional[float] = None
    sales_price_cost_share: Optional[float] = None
    rows_per_page: Optional[int] = None
    store: Optional[int] = None

class SignupData(BaseModel):
    name: Optional[str]
    email: str
    phone: str
    password: str
    location: Optional[str]
    register_type: Optional[str]
    agree: bool


@cached(cache=TTLCache(maxsize=10, ttl=600)) # 600 ~ 10 min
def get_customer_id_from_username(username:str):
    """
    Get the customer id from the username
    :param username: The username of the user
    :return: The customer id
    """
    with spaces.SpaceDict('./config.json') as config:
        return config["users"][username]["customer_id"]


def read_forecast(username: str, recalculate=False):
    """
    Read the forecast for a user
    :param username: The username of the user
    :param recalculate: If True, recalculate the forecast
    :return: The forecast
    """
    customer_id = get_customer_id_from_username(username)
    if recalculate:
        spaces.recalculate_forecast(customer_id)
        _forecast_cache.clear()

    return read_cached_forecast(customer_id)


_forecast_cache = TTLCache(maxsize=10, ttl=600)
@cached(cache=_forecast_cache) # 600 ~ 10 min
def read_cached_forecast(customer_id: str):
    with spaces.SpaceDict(f'./forecast_{customer_id}.json') as forecast:
        return forecast


def update_user_settings(username:str, user_settings: UserSettings):
    """
    Update the user settings for a user
    :param username: The username of the user
    :param user_settings: The new user settings
    :return: True if the user settings were updated, else False
    """

    # only update cols that are not None
    updates = [(k,v) for k,v in user_settings if v is not None]

    with spaces.SpaceDict('./config.json') as config:
        config["users"][username].update(updates)
        customer_id = config["users"][username]["customer_id"]
        config["customers"][customer_id].update(updates)
        return True


def read_user_settings(username:str):
    """
    Read the user settings for a user
    :param username: The username of the user
    :return: The user settings
    """
    with spaces.SpaceDict('./config.json') as config:
        user = config["users"][username]
        customer_id = user["customer_id"]
        customer = config["customers"][customer_id]
        store = user["store"]
        store = customer["stores"][str(store)]
        register = customer["register"]
        result = {**customer, **register, **user, **store}
        result.pop("register")
        result.pop("signup_id")
        result.pop("hashed_password")
        stores = []
        for s in result['stores']:
            store = result['stores'][s]
            store['id'] = s
            stores.append(store)
        result['stores'] = stores
        if result["disabled"]:
            result = {}
        return result


def read_users():
    """
    Read the list of users
    :return: dict of user settings
    """
    with spaces.SpaceDict('./config.json') as config:
        return config["users"]


def create_signup(signup_data: SignupData):
    """write registration to database, create user and customer so that user can login in next step"""
    with spaces.SpaceDict('./config.json') as config:
        # get next available signup_id
        signup_id = str(max([int(k) for k in config["signups"].keys()]) + 1)
        config["signups"][signup_id] = {
            "name": signup_data.name,
            "email": signup_data.email.lower(),
            "phone": signup_data.phone,
            "password": signup_data.password,
            "location": signup_data.location,
            "register_type": signup_data.register_type,
            "agree": signup_data.agree
        }
        # create customer
        customer_id = str(max([int(k) for k in config["customers"].keys()]) + 1)
        customer = {
          "register":{
            "register_plugin":"plugins.manual.manual",
            "register_plugin_name":"manueller Import"
          },
          "login_valid_minutes":129600,
            "returns_current": 250,
            "sales_price_cost_share": 0.35,
          "stores":{
             "1":{
                "country":"DE",
                "state":"HE",
                "city":"Wiesbaden",
                "store_name":signup_data.location
             }
          }
        }
        config["customers"][customer_id] = customer
        # create user
        user = {
            "signup_id": signup_id,
            "hashed_password": signup_data.password,
            "customer_id": customer_id,
            "store": 1,
            "display_name": signup_data.name,
            "rows_per_page": 10,
            "disabled": False
        }
        config["users"][signup_data.email] = user

        return f'signup, customer and user with email {signup_data.email} created'

