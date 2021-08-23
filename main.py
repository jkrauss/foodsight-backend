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

import importlib
import glob
import sys, os, io
import schedule
from schedule import every, repeat
import time
import uvicorn
import datetime as dt
import pathlib
import base64

import multiprocessing as mp

import requests
import json

from main_auth import get_current_active_user, authenticate_user, create_access_token, User, Token, ACCESS_TOKEN_EXPIRE_MINUTES

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
    return FileResponse('client/public/index.html')


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

    return settings


class UserSettings(BaseModel):
    tomorrow: Optional[bool] = None
    day_after_tomorrow: Optional[bool] = None
    next_seven_days: Optional[bool] = None
    rows_per_page: Optional[int] = None
    login_valid_minutes: Optional[int] = None
    store_name: Optional[str] = None


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

    for k, v in edit.items():
        if v is not None:
            if k in config['base']:
                config['base'][k] = v
            else:
                config['users'][ix][k] = v

    # write to file
    with open("pipeline/data/customer.toml", "w") as f:
        toml.dump(config, f)

class ProblemReport(BaseModel):
    problem_text: str
    screenshot: str


@app.post("/api/problem")
def post_problem(problem_report: ProblemReport):
    try:
        now = dt.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        dir_str = f"pipeline/data/problem_reports/report_{now}"
        dir = pathlib.Path(dir_str)
        dir.mkdir(parents=False, exist_ok=False)

        screen_path = dir / "screenshot.png"
        message_path = dir / "message.txt"

        screen = base64.b64decode(problem_report.screenshot.split(',')[1])
        screen_path.write_bytes(screen)
        message_path.write_text(problem_report.problem_text)

        slack_url = "https://hooks.slack.com/services/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"
        img_url = f"https://foodsight.ml4all.com/api/problems/report_{now}/screenshot.png"

        payload = {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": problem_report.problem_text
                    }
                },
            {
                "type": "image",
                "title": {
                    "type": "plain_text",
                    "text": "Please enjoy this photo of a kitten"
                },
                "block_id": "image4",
                "image_url": img_url,
                "alt_text": "An incredibly cute kitten."
                }
            ]
        }

        r = requests.post(url=slack_url, data=json.dumps(payload))
        print(r.status_code, r.reason)
        print(r.text[:300])
        print(json.dumps(payload))

        return True
    except:
        print("Error saving problem_report:", sys.exc_info()[0])
        return False


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
app.mount('/', StaticFiles(directory="client/public/"), name="static")


########################
### PIPELINE SECTION ###
########################

# required so that plugins can be loaded 
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(HERE+'/pipeline')

def _import(pipeline, step):
    """Import the given plugin file from a package"""
    return importlib.import_module(f"{pipeline}.{step}")

#@repeat(every(6*60).minutes, 'pipeline') # 4 times a day - every 6 hours
    #print(f"pipeline run started at {dt.datetime.now()}")
    
def _import_pipeline(pipeline):

    cwd = os.getcwd()

    """import all steps/modules of the folder/package 'pipeline' in alphabetical order"""
    flist = list()
    for filepath in glob.iglob(f'{pipeline}/*.py'):
        if filepath != f'{pipeline}/util.py':
            flist.append(filepath)

    # this sorts the original list in place - handy for a sequential pipeline
    flist.sort()

    pipeline_steps = list()
    steps = [f[:-3] for f in flist if f[0] != "_"]
    for step in steps:
        pipeline_steps.append(_import(*step.split('/')))

    os.chdir(cwd)
    
    return pipeline_steps

def run_pipeline(pipeline_steps):
    print(f'starting pipeline run at {dt.datetime.now()}')
    for step in pipeline_steps:
        step.run()
    try:
        # run whole pipeline or break, but without breaking the process
        for step in pipeline_steps:
            step.run()
    except Exception as e:
        print(f'pipeline run failed in step {str(step)} at {dt.datetime.now()}, exception below..')
        print(e)
    else:
        print(f'pipeline completed successfully at {dt.datetime.now()}')


# not required in main.py was used in startup.py
def start_uvi():
    print(os.getcwd())
    #os.system('uvicorn main:app')
    uvicorn.run("main:app", host="0.0.0.0", port=8000, log_level="info")

def start_schedule(pipeline_steps):

    schedule.every().day.at('03:00').do(run_pipeline, pipeline_steps)
    #schedule.every().day.at('09:00').do(run_pipeline, pipeline_steps)
    schedule.every().day.at('15:00').do(run_pipeline, pipeline_steps)
    #schedule.every().day.at('21:00').do(run_pipeline, pipeline_steps)    

    #schedule.every(10).minutes.do(run_pipeline, pipeline_steps)
    # run_pipeline(pipeline_steps)

    while True:
        schedule.run_pending()
        time.sleep(10)

os.environ["CONFIG_DIR"] = os.getcwd()

# import all steps/modules of the folder/package in alphabetical order
pipeline_steps = _import_pipeline('pipeline')

#p1 = mp.Process(target=start_uvi, name='uvicorn')
p2 = mp.Process(target=start_schedule, args=(pipeline_steps,), name='pipeline')

#p1.start()
p2.start()