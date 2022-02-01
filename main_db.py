import sqlite3 as sql
import pandas as pd
from pydantic import BaseModel
from typing import Optional

import pathlib
import shutil

import main_auth as auth

import json

# Naming convention: create_..., read_..., update_..., delete_...

__db = 'pipeline/data/food.db'

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


def _get_customer_id_from_username(username:str):
    with sql.connect(__db) as conn:
        cur = conn.cursor()
        cur.execute(f"""
        select customer_id 
        from user u
        where u.username= '{username}'
        """)
        customer_id = cur.fetchall()[0][0]
        return customer_id


def read_forecast(username: str):
    customer_id = _get_customer_id_from_username(username)
    # forecast = pd.read_csv(f'pipeline/data/customer/{customer_id}/6_predict/predictions.csv')
    forecast = json.load(open(f'pipeline/data/customer/{customer_id}/6_predict/predictions.json'))
    return forecast


def update_user_settings(username:str, user_settings: UserSettings):
    
    # only update cols that are not None
    updates = [(k,v) for k,v in user_settings if v is not None]

    # Append a set statement for each
    statement = "UPDATE user SET"
    for u in updates:
        if u[0] != 'username':
            statement += f"""
            {u[0]}={u[1]},"""
    statement = statement[:-1] #remove last comma
    statement += f"""
    WHERE username='{username}'
    ORDER BY id
    LIMIT 1;
    """

    if len(statement.splitlines()) > 4: # there are actually cols to be updated
        print(statement)
        with sql.connect(__db) as conn:
            cur = conn.cursor()
            cur.execute(statement)


def read_user_settings(username:str):
    with sql.connect(__db) as conn:
        # retrieve user-specific props
        result = pd.read_sql(f"""
            select u.username
			, u.rows_per_page
			, u.returns_current
			, u.sales_price_cost_share
			, r.register_plugin
			, r.register_plugin_name
			, s.country
			, s.state
			, s.city
			, u.store
			, s.store_name
            , u.customer_id
			, c.login_valid_minutes
            from user u
                inner join customer c
                    on u.customer_id = c.id
                inner join register r
                    on c.register_id = r.id
                inner join store s
                    on u.store = s.id
                where u.username = '{username}'
                and u.disabled = 0
        """, conn)
        # transform to dict
        result = result.to_dict(orient='records')[0]

        # retrieve stores that the customer of this user has
        customer_id = result['customer_id']
        stores = pd.read_sql(f"""
            select s.id as "store"
                    , s.country
                    , s.state
                    , s.city
                    , s.store_name
            from store s
            where customer_id = {customer_id}
        """, conn)

        # insert stores into resultset as a list of dict
        stores = stores.to_dict(orient='records')
        result['stores'] = stores

        return result


def read_users():
        with sql.connect(__db) as conn:
        # retrieve user-specific props
            result = pd.read_sql(f"""
                select u.username
                , u.display_name
                , u.hashed_password
                , u.disabled
                from user u
            """, conn)

        # transform to dict
        return result.to_dict(orient='records')


def create_signup(signup_data: SignupData):
    """write registration to database, create user and customer so that user can login in next step"""
    # TODO: implement multiple users per customer
    # TODO: correctly determine store-fields: country, state, city, e.g. call HERE.com-api

    with sql.connect(__db) as conn:
        cur = conn.cursor()

        # create new signup in db
        statement = f"""
            INSERT INTO signup (name, email, phone, password, location, register_type, agree)
            VALUES( '{signup_data.name}', '{signup_data.email}', '{signup_data.phone}', 
            '{signup_data.password}', '{signup_data.location}', '{signup_data.register_type}'
            , {signup_data.agree});
            """
        cur.execute(statement)
        signup_id = cur.lastrowid

        # check if a user with that email-address already exists
        cur.execute(f"select u.id from user u where u.username='{signup_data.email}'")
        if ( len(cur.fetchall()) > 0):
            return f'user with email {signup_data.email} already existing'
        else:            
            # retrieve id of register / type manual
            cur.execute("select id from register r where r.register_plugin='plugins.manual.manual'")
            register_id = cur.fetchall()[0][0]

            # create new customer
            statement = f"""
            INSERT INTO customer (register_id, login_valid_minutes)
            VALUES ({register_id}, 129600)
            """
            cur.execute(statement)
            customer_id = cur.lastrowid

            # create new store
            statement = f"""
            INSERT INTO store (customer_id, country, state, city, store_name)
            VALUES ({customer_id}, 'DE', 'HE', 'Wiesbaden', '{signup_data.location}')
            """
            cur.execute(statement)
            store_id = cur.lastrowid

            # create new user
            statement = f"""
            INSERT INTO user (customer_id, signup_id, username, display_name,
                hashed_password, disabled, rows_per_page,
                tomorrow, day_after_tomorrow, next_seven_days, store)
            VALUES ({customer_id}, {signup_id}, '{signup_data.email}', '{signup_data.name}',
                '{signup_data.password}', 0, 10,
                1,0,0,{store_id}
            )
            """
            cur.execute(statement)

            create_pipeline(customer_id)


            return f'signup, customer and user with email {signup_data.email} created'


def create_pipeline(customer_id: int):
    """creates a new folder for the customer-data and fills with template-data """
    base_path = pathlib.Path(f'./pipeline/data/customer/')
    cust_path = base_path/str(customer_id)

    source_path = base_path/'0'
    shutil.copytree(source_path, cust_path)


def run_pipeline(username: str):
    customer_id = _get_customer_id_from_username(username)    
    from startup_pipeline import run_pipeline
    run_pipeline(customer_id=customer_id)


def init_db(delete=False):
    """initialize database, if entities exist either do nothing (delete=False, default) or purge (delete=True)"""
    # TODO: implement delete=True
    with sql.connect(__db) as conn:
        cur = conn.cursor()
        # create user-table
        cur.execute("""
        CREATE TABLE "user" (
            "id"	INTEGER,
            "customer_id" integer,
            "signup_id" integer,
            "username"	text,
            "display_name"	text,
            "hashed_password"	text,
            "disabled"	integer,
            "rows_per_page"	integer,
            "tomorrow"	integer,
            "day_after_tomorrow"	integer,
            "next_seven_days"	integer,
            "store"	integer,
            PRIMARY KEY("id" AUTOINCREMENT)
        );"""
            )
        # create customer-table
        cur.execute("""
            CREATE TABLE "customer" (
                "id"	INTEGER,
                "register_id"	integer,
                "login_valid_minutes"	integer,
                PRIMARY KEY("id" AUTOINCREMENT)
            );"""
            )
        # create store-table
        cur.execute("""
        CREATE TABLE "store" (
            "id"	INTEGER,
            "customer_id"	integer,
            "country"	text,
            "state"	text,
            "city"	text,
            "store_name"	text,
            PRIMARY KEY("id" AUTOINCREMENT)
        );"""
            )
        # create register-table
        cur.execute("""
        CREATE TABLE "register" (
            "id"	INTEGER,
            "register_plugin"	text,
            "register_plugin_name"	text,
            PRIMARY KEY("id" AUTOINCREMENT)
        );"""
            )
        # create editable-properties-table
        cur.execute("""
        CREATE TABLE "editable_property" (
            "id"	INTEGER,
            "property"	text,
            PRIMARY KEY("id" AUTOINCREMENT)
        );"""
            )
        # create signup-table
        cur.execute("""
        CREATE TABLE "signup" (
            "id"	INTEGER,
            "name"	text,
            "email"	text,
            "phone"	text,
            "password"	text,
            "location"	text,
            "register_type"	,
            "agree"	integer,
            PRIMARY KEY("id" AUTOINCREMENT)
        );"""
            )
        conn.commit()
