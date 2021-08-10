from fastapi import FastAPI
from fastapi import status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import pandas as pd

from main_auth import *

import toml


# TODO: UI: Select how many days of forecast to pull
# TODO: UI & API: Button to generate and deliver pdf of completed order
# TODO: Write unit tests that ensure authentication and authorization do work
# TODO: Does implementing client_id and client_secret help security?

# preload forecasts

app = FastAPI()

config = toml.load('customer.toml')

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
def get_forecast(store:int, days:int=1, current_user: User = Depends(get_current_active_user)):


#def get_forecast(store:int, days:int=1):

    try:
        days = int(days)
        store = int(store)
    except:
        return status.HTTP_422_UNPROCESSABLE_ENTITY , {'days and store both must be integers'}
    
    # days must be between 1 and 7
    if days < 1:
        days = 1
    if days > 7:
        days = 7
    
    forecasts = pd.read_csv('pipeline/data/6_predict/predictions.csv')
    # store must be in forecasts
    found = forecasts[forecasts.store==store]
    if len(found)==0:
        return status.HTTP_422_UNPROCESSABLE_ENTITY , {f'store with id {store} is not known.'}
    

    dates = forecasts.date.unique()
    dates.sort()

    # filter and format a bit
    result = found[forecasts.date.isin(dates[:days])][['date', 'product', 'sales_prediction']].reset_index(drop=True).reset_index()
    result.columns=['id', 'date', 'product', 'forecast']


    # TODO: do a proper calculation of order-range instead of this 
    result['order_from'] = (result.forecast*0.8).apply(round).apply(str)
    result['order_to'] = (result.forecast*1.2).apply(round).apply(str)
    result['order_range'] = result.order_from + ' - ' + result.order_to
    result = result.drop(['order_from', 'order_to'], axis=1)

    result.forecast = result.forecast.apply(round)
    result['order_qty'] = result.forecast

    result['comment'] = ''
    result.to_json(orient='records')
    return result.to_dict(orient='records') #FileResponse('client/public/tableData.json')


# actual API method that delivers tokens on successful login
@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falscher Benutzername oder Passwort",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


# secured API-method that returns user data if token is valid
@app.get("/api/usersettings/")
def get_usersettings(current_user: User = Depends(get_current_active_user)):

    user_settings = dict([u for u in config['users'] if u['username']==current_user.username][0])

    del user_settings['hashed_password']
    del user_settings['disabled']

    settings = {**config['base'], **user_settings}

    return settings


# Place After All Other Routes
app.mount('/', StaticFiles(directory="client/public/"), name="static")
