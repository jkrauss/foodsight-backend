from fastapi import FastAPI
from fastapi import status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from typing import Optional

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
def get_forecast(store:int, current_user: User = Depends(get_current_active_user)):
    
    forecasts = pd.read_csv('pipeline/data/6_predict/predictions.csv')
    # store must be in forecasts
    found = forecasts[forecasts.store==store]
    if len(found)==0:
        return status.HTTP_422_UNPROCESSABLE_ENTITY , {f'store with id {store} is not known.'}

    dates = forecasts.date.unique()
    dates.sort()
    print("dates in forecast: ", dates)

    # filter and format a bit
    result = found[forecasts.date.isin(dates[:7])][['date', 'product', 'sales_prediction']].reset_index(drop=True).reset_index()
    result.columns=['id', 'date', 'product', 'forecast']

    # TODO: do a proper calculation of order-range instead of this 
    result['order_from'] = (result.forecast*0.8).apply(round)#.apply(str)
    result['order_to'] = (result.forecast*1.2).apply(round)#.apply(str)

    result.forecast = result.forecast.apply(round)

    # build 3 frames: tomorrow, day_after, seven_days
    tomorrow = result[result.date==dates[0]][['product', 'forecast', 'order_from', 'order_to']]
    day_after = result[result.date==dates[1]][['product', 'forecast', 'order_from', 'order_to']]
    seven_days = result[['product', 'forecast', 'order_from', 'order_to']].groupby('product').sum().reset_index()

    tomorrow['tomorrow_order_range'] = tomorrow.order_from.apply(str) + ' - ' + tomorrow.order_to.apply(str)
    day_after['day_after_order_range'] = day_after.order_from.apply(str) + ' - ' + day_after.order_to.apply(str)
    seven_days['next7_order_range'] = seven_days.order_from.apply(str) + ' - ' + seven_days.order_to.apply(str)

    tomorrow = tomorrow[['product', 'forecast', 'tomorrow_order_range']]
    tomorrow.columns = ['product', 'tomorrow_order_qty', 'tomorrow_order_range']
    day_after = day_after[['product', 'forecast', 'day_after_order_range']]
    day_after.columns = ['product', 'day_after_order_qty', 'day_after_order_range']
    seven_days = seven_days[['product', 'forecast', 'next7_order_range']]
    seven_days.columns = ['product', 'next7_order_qty', 'next7_order_range']

    result = pd.merge(pd.merge(tomorrow, day_after, left_on='product', right_on='product')
        , seven_days, left_on='product', right_on='product')


    result.to_json(orient='records')
    return result.to_dict(orient='records') #FileResponse('client/public/tableData.json')


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
    with open("customer.toml", "w") as f:
        toml.dump(config, f)

class ProblemReport(BaseModel):
    problem_text: str
    screenshot: str


@app.post("/api/problem")
def post_problem(problem_report: ProblemReport):
    return True

# Place After All Other Routes
app.mount('/', StaticFiles(directory="client/public/"), name="static")
