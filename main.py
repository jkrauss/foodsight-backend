from fastapi import FastAPI
from fastapi import status, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from typing import Optional
from pydantic import BaseModel

import pandas as pd
import toml

import sys
import datetime as dt
import pathlib
import base64

import requests
import json

from main_auth import get_current_active_user, authenticate_user
from main_auth import create_access_token, get_password_hash
from main_auth import User, Token, ACCESS_TOKEN_EXPIRE_MINUTES, SLACK_URL

#######################
### UVICORN SECTION ###
#######################

app = FastAPI()
config = toml.load('pipeline/data/customer.toml')
origins = ["*"]
# to deactivate CORS completely...
#origins = [
#    "*"
#]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get('/')
def home():
    return FileResponse('client/dist/index.html')


@app.get('/api/forecast/')
def get_forecast(store:int, current_user: User = Depends(get_current_active_user)):
    
    forecasts = pd.read_csv('pipeline/data/6_predict/predictions.csv')
    # store must be in forecasts
    found = forecasts[forecasts.store==store]
    if len(found)==0:
        return status.HTTP_422_UNPROCESSABLE_ENTITY , {f'store with id {store} is not known.'}

    found = found.drop('store', axis=1)
    return found.to_dict(orient='records') #FileResponse('client/public/tableData.json')


# actual API method that delivers tokens on successful login
@app.post("/api/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falscher Benutzername oder Passwort",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = dt.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token, expire_dt = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "expires": str(expire_dt)}


# secured API-method that returns user data if token is valid
@app.get("/api/usersettings/")
def get_usersettings(current_user: User = Depends(get_current_active_user)):

    user_settings = dict([u for u in config['users'] if u['username']==current_user.username][0])

    del user_settings['hashed_password']
    del user_settings['disabled']
    settings = {**config['base'], **user_settings}
    settings['stores'] = config['stores']

    return settings


class UserSettings(BaseModel):
    tomorrow: Optional[bool] = None
    day_after_tomorrow: Optional[bool] = None
    next_seven_days: Optional[bool] = None
    rows_per_page: Optional[int] = None
    login_valid_minutes: Optional[int] = None
    store_name: Optional[str] = None
    store: Optional[int] = None


@app.put("/api/usersettings/")
def put_usersettings(user_settings: UserSettings, current_user: User = Depends(get_current_active_user)):

    # determine index of current user's settings in config['users'] :> ix
    ix = -1
    n = len(config['users'])
    for i in range(n):
        if config['users'][i]['username'] == current_user.username:
            ix = i
    # no user found
    if ix == -1:
        return JSONResponse(status_code=422, content={"message": f"No configuration found for user {current_user.username}"})

    # consider only values that are whitelisted for editing
    # TODO: What if usersettings is empty?
    edit = {k: v for k,v in vars(user_settings).items() if k in config['base']['editable_properties']}

    # does the update contain a store?
    # do we have this store in our settings?
    # set base-level store-related fields to the fields of the found store
    if edit['store'] is not None:
        for store_settings in config['stores']:
            if edit['store'] == store_settings['store']:
                config['base']['store'] = store_settings['store']
                config['base']['state'] = store_settings['state']
                config['base']['city'] = store_settings['city']
                config['base']['store_name'] = store_settings['store_name']
        del edit['store']

    for k, v in edit.items():
        if v is not None:
            if k in config['base']:
                config['base'][k] = v
            else:
                config['users'][ix][k] = v

    # write to file
    with open("pipeline/data/customer.toml", "w") as f:
        toml.dump(config, f)

    return get_usersettings(current_user)

class ProblemReport(BaseModel):
    problem_text: str
    screenshot: Optional[str] = None


@app.post("/api/problem")
def post_problem(problem_report: ProblemReport):
    try:
        now = dt.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        dir_str = f"pipeline/data/problem_reports/report_{now}"
        dir = pathlib.Path(dir_str)
        dir.mkdir(parents=False, exist_ok=False)

        screen_path = dir / "screenshot.png"
        message_path = dir / "message.txt"

        if problem_report.screenshot:
            screen = base64.b64decode(problem_report.screenshot.split(',')[1])
            screen_path.write_bytes(screen)
        
        message_path.write_text(problem_report.problem_text)

        
        img_url = f"https://foodsight.ml4all.com/api/problems/report_{now}/screenshot.png"

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": problem_report.problem_text
                    }
            }
        ]
        if problem_report.screenshot:
            blocks.append(
                 {
                    "type": "image",
                    "title": {
                        "type": "plain_text",
                        "text": "User screenshot:"
                    },
                    "block_id": "image4",
                    "image_url": img_url,
                    "alt_text": "screenshot taken from a foodsight user"
                }               
            )

        payload = json.dumps({"blocks": blocks})

        r = requests.post(url=SLACK_URL, data=payload)
        print("posted problem-report to slack, result... ")
        print(r.status_code, r.reason)
        print(r.text[:300])
        print(json.dumps(payload))

        return True
    except:
        print("Error saving problem_report:", sys.exc_info()[0])
        return False


class SignupData(BaseModel):
    name: Optional[str]
    email: str
    phone: str
    password: str
    location: Optional[str]
    register_type: Optional[str]
    agree: bool


@app.post("/api/signup")
def post_signup(signup_data: SignupData):
    hash = get_password_hash(signup_data.password)

    slack_text = f"""
    
    *** WOHOO! WIR HABEN EINE NEUE ANMELDUNG! ***

    name: {signup_data.name}
    email: {signup_data.email}
    phone: {signup_data.phone}
    password: {hash}
    location: {signup_data.location}
    register_type: {signup_data.register_type}
    agree: {signup_data.agree}
        """

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": slack_text
                }
        }
    ]

    payload = json.dumps({"blocks": blocks})

    r = requests.post(url=SLACK_URL, data=payload)
    print("posted new signup to slack, result... ")
    print(r.status_code, r.reason)
    print(r.text[:300])
    #print(json.dumps(payload))



class OrderData(BaseModel):
    data: list
    option: str
    order_option: str


@app.post("/api/order")
def post_order(order_data: OrderData):
    df = pd.DataFrame.from_records(data=order_data.data)

    df.rename(mapper={
            'id': 'ID',
            'product': "Produkt",
            'tomorrow_order_qty': 'Bestellung Morgen',
            'day_after_order_qty': 'Bestellung Übermorgen',
            'next7_order_qty': 'Bestellung nächste 7 Tage',
        }, axis=1, inplace=True, errors='raise')

    if order_data.order_option == 'tomorrow':
        df = df.drop(['day_after_order_range'
            , 'Bestellung Übermorgen'
            , 'next7_order_range'
            , 'Bestellung nächste 7 Tage'
            , 'tomorrow_order_range'], axis=1)
    elif order_data.order_option == 'day_after_tomorrow':
        df = df.drop(['tomorrow_order_range'
            , 'Bestellung Morgen'
            , 'next7_order_range'
            , 'Bestellung nächste 7 Tage'
            , 'day_after_order_range'], axis=1)
    elif order_data.order_option == 'next_seven_days':
        df = df.drop(['day_after_order_range'
            , 'Bestellung Übermorgen'
            , 'tomorrow_order_range'
            , 'Bestellung Morgen'
            , 'next7_order_range'], axis=1)

    if order_data.option == 'xlsx':
        f = "pipeline/data/Foodsight_Bestellung.xlsx"
        mt = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        df.to_excel(f, index=False)
        return FileResponse(path=f, media_type=mt, filename="Foodsight_Bestellung.xlsx")
    else:
        return df.to_csv(index=False)


# Place After All Other Routes

app.mount("/api/problems", StaticFiles(directory="pipeline/data/problem_reports"), name="problems")
app.mount('/', StaticFiles(directory="client/dist/"), name="static")
