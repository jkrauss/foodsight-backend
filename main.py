from fastapi import FastAPI, File, UploadFile, BackgroundTasks
from fastapi import status, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from typing import Optional
from pydantic import BaseModel

import pandas as pd
import aiofiles

import sys
import datetime as dt
import pathlib
import base64

import requests
import json

from main_auth import get_current_active_user, authenticate_user
from main_auth import create_access_token, get_password_hash
from main_auth import Token, SLACK_URL

import main_db as db

app = FastAPI()
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


#@app.get('/')
#def home():
#    return FileResponse('client/dist/__app.html')


@app.get('/api/forecast/')
def get_forecast(store:int, current_user: db.User = Depends(get_current_active_user)):
    
    forecasts = db.read_forecast(current_user.username)
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
    mins = db.read_user_settings(user.username)['login_valid_minutes']
    access_token_expires = dt.timedelta(minutes=mins)
    access_token, expire_dt = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "expires": str(expire_dt)}


# secured API-method that returns user data if token is valid
@app.get("/api/usersettings/")
def get_usersettings(current_user: db.User = Depends(get_current_active_user)):

    settings = db.read_user_settings(current_user.username)
    if len(settings)==0:
        return JSONResponse(status_code=422, content={"message": f"No configuration found for user {current_user.username}"})

    return settings


@app.put("/api/usersettings/")
def put_usersettings(user_settings: db.UserSettings, current_user: db.User = Depends(get_current_active_user)):
    db.update_user_settings(current_user.username, user_settings)
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


@app.post("/api/signup")
def post_signup(signup_data: db.SignupData, background_tasks: BackgroundTasks):
    hash = get_password_hash(signup_data.password)
    signup_data.password = hash

    db.create_signup(signup_data)

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


@app.post("/api/sales_upload")
async def post_sales_upload(file: UploadFile = File(...), current_user: db.User = Depends(get_current_active_user)):
    
    customer_id = db._get_customer_id_from_username(current_user.username)

    async with aiofiles.open(f"pipeline/data/customer/{customer_id}/0_raw/manual/manual_import.xlsx", 'wb') as out_file:
        while content := await file.read(1024):  # async read chunk
            await out_file.write(content)  # async write chunk
    # TODO: HIER WEITER!!
    # background_tasks.add_task(db.run_pipeline, signup_data.email)
    db.run_pipeline(current_user.username)
    return {"filename": file.filename}


# Place After All Other Routes 
app.mount("/api/problems", StaticFiles(directory="pipeline/data/problem_reports"), name="problems")
#app.mount('/', StaticFiles(directory="client/dist/"), name="static")
