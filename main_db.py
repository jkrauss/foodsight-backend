#import sqlite3 as sql
import pandas as pd
from pydantic import BaseModel
from typing import Optional

import pathlib
import shutil

import main_auth as auth

import json

import boto3
import botocore.exceptions
import os
import dotenv

from cachetools import cached, TTLCache

dotenv.load_dotenv()
# Naming convention: create_..., read_..., update_..., delete_...

#__db = 'pipeline/data/food.db'


class SpaceDict(object):
    """
    Class to read and write to dict/json that is in the S3 bucket - batteries included (context manager)
    """

    def __upload_file(self, file_name: str):
        """Upload a file to the S3 bucket

        :param file_name: File to upload
        :return: True if file was uploaded, else False
        """

        # use filename as object_name
        object_name = os.path.basename(file_name)

        # create client
        session = boto3.session.Session()
        client = session.client('s3',
                            region_name='us-east-1', # is mainly ignored but validated by boto3
                            endpoint_url=os.getenv('SPACES_URL'), 
                            aws_access_key_id=os.getenv('SPACES_KEY'),
                            aws_secret_access_key=os.getenv('SPACES_SECRET'))

        # Upload the file
        try:
            client.upload_file(file_name, os.getenv('SPACES_BUCKET_NAME'), object_name)
        except botocore.exceptions.ClientError as e:
            print(e)
            return False
        return True

    def __download_file(self, file_name: str):
        """Download a file from the S3 bucket

        :param file_name: File to upload
        :return: True if file was uploaded, else False
        """

        # use filename as object_name
        object_name = os.path.basename(file_name)

        # create client
        session = boto3.session.Session()
        client = session.client('s3',
                            region_name='us-east-1', # is mainly ignored but validated by boto3
                            endpoint_url=os.getenv('SPACES_URL'),
                            aws_access_key_id=os.getenv('SPACES_KEY'),
                            aws_secret_access_key=os.getenv('SPACES_SECRET'))

        # Upload the file
        try:
            client.download_file(os.getenv('SPACES_BUCKET_NAME'), object_name, file_name)
        except botocore.exceptions.ClientError as e:
            print(e)
            return False
        return True

    def __init__(self, config_file: str):
        """
        Constructor
        :param config_file: The name of the config file in the S3 bucket
        """
        if self.__download_file(config_file):
            self.file_obj = json.load(open(config_file))
            self.file_path = config_file
        else:
            self.file_obj = {}

    def __enter__(self):
        return self.file_obj

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            json.dump(self.file_obj, open(self.file_path, 'w'))
            try:
                self.__upload_file(self.file_path)
            except :
                print('Error uploading config file')
        else:
            print('Error: {}'.format(exc_val))
            return False
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


def read_forecast(username: str, recalculate=False):
    """
    Read the forecast for a user
    :param username: The username of the user
    :param recalculate: If True, recalculate the forecast
    :return: The forecast
    """
    if recalculate:
        # TODO: implement!
        return read_cached_forecast(username)
    else:
        return read_cached_forecast(username)


@cached(cache=TTLCache(maxsize=10, ttl=600)) # 600 ~ 10 min
def read_cached_forecast(username: str):
    with SpaceDict('./config.json') as config:
        customer_id = config["users"][username]["customer_id"]

    with SpaceDict('./forecast.json') as forecast:
        return forecast[customer_id]


def update_user_settings(username:str, user_settings: UserSettings):
    """
    Update the user settings for a user
    :param username: The username of the user
    :param user_settings: The new user settings
    :return: True if the user settings were updated, else False
    """

    # only update cols that are not None
    updates = [(k,v) for k,v in user_settings if v is not None]

    with SpaceDict('./config.json') as config:
        config["users"][username].update(updates)
        return True


def read_user_settings(username:str):
    """
    Read the user settings for a user
    :param username: The username of the user
    :return: The user settings
    """
    with SpaceDict('./config.json') as config:
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
    with SpaceDict('./config.json') as config:
        return config["users"]


def create_signup(signup_data: SignupData):
    """write registration to database, create user and customer so that user can login in next step"""
    with SpaceDict('./config.json') as config:
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
            "returns_current": 250,
            "sales_price_cost_share": 0.35,
            "rows_per_page": 10,
            "disabled": False
        }
        config["users"][signup_data.email] = user

        return f'signup, customer and user with email {signup_data.email} created'

