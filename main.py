"""Foodsight API — Bakery sales prediction and order planning.

Serves the Svelte frontend and exposes REST endpoints for
authentication, forecast retrieval, user settings, order export,
problem reports, and sign-ups.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import pathlib
import sys

import pandas as pd
import requests
import toml
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

from main_auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    SLACK_URL,
    Token,
    User,
    authenticate_user,
    create_access_token,
    get_current_active_user,
    get_password_hash,
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Foodsight API", version="1.0.0")

config = toml.load("pipeline/data/customer.toml")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------

@app.get("/")
def home():
    """Serve the single-page Svelte application."""
    return FileResponse("client/public/index.html")


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

@app.post("/api/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """Authenticate a user and return a JWT access token."""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = dt.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token, expire_dt = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "expires": str(expire_dt)}


# ---------------------------------------------------------------------------
# Forecasts
# ---------------------------------------------------------------------------

@app.get("/api/forecast/")
def get_forecast(store: int, current_user: User = Depends(get_current_active_user)):
    """Return the latest sales predictions for the given store."""
    forecasts = pd.read_csv("pipeline/data/6_predict/predictions.csv")
    found = forecasts[forecasts.store == store]
    if len(found) == 0:
        return JSONResponse(
            status_code=422,
            content={"message": f"Store {store} is not known."},
        )
    found = found.drop("store", axis=1)
    return found.to_dict(orient="records")


# ---------------------------------------------------------------------------
# User settings
# ---------------------------------------------------------------------------

class UserSettings(BaseModel):
    tomorrow: Optional[bool] = None
    day_after_tomorrow: Optional[bool] = None
    next_seven_days: Optional[bool] = None
    rows_per_page: Optional[int] = None
    login_valid_minutes: Optional[int] = None
    store_name: Optional[str] = None
    store: Optional[int] = None


@app.get("/api/usersettings/")
def get_usersettings(current_user: User = Depends(get_current_active_user)):
    """Return merged base + user-specific settings."""
    user_settings = next(
        u for u in config["users"] if u["username"] == current_user.username
    )
    safe = {k: v for k, v in user_settings.items() if k not in ("hashed_password", "disabled")}
    settings = {**config["base"], **safe}
    settings["stores"] = config["stores"]
    return settings


@app.put("/api/usersettings/")
def put_usersettings(user_settings: UserSettings, current_user: User = Depends(get_current_active_user)):
    """Update editable user settings and persist to config."""
    ix = next(
        (i for i, u in enumerate(config["users"]) if u["username"] == current_user.username),
        -1,
    )
    if ix == -1:
        return JSONResponse(status_code=422, content={"message": f"No config for user {current_user.username}"})

    allowed = set(config["base"]["editable_properties"])
    edit = {k: v for k, v in user_settings.model_dump().items() if k in allowed}

    # Switch store context if a new store was selected
    if edit.get("store") is not None:
        store_match = next(
            (s for s in config["stores"] if s["store"] == edit["store"]), None
        )
        if store_match:
            for key in ("store", "state", "city", "store_name"):
                config["base"][key] = store_match[key]
        del edit["store"]

    for k, v in edit.items():
        if v is not None:
            target = config["base"] if k in config["base"] else config["users"][ix]
            target[k] = v

    with open("pipeline/data/customer.toml", "w") as f:
        toml.dump(config, f)

    return get_usersettings(current_user)


# ---------------------------------------------------------------------------
# Problem reports
# ---------------------------------------------------------------------------

class ProblemReport(BaseModel):
    problem_text: str
    screenshot: Optional[str] = None


def _post_to_slack(payload: dict) -> None:
    """Send a Slack notification. Silently fails if webhook is unreachable."""
    try:
        requests.post(url=SLACK_URL, data=json.dumps(payload), timeout=5)
    except requests.RequestException:
        pass


@app.post("/api/problem")
def post_problem(problem_report: ProblemReport):
    """Save a user-submitted problem report and notify via Slack."""
    now = dt.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    report_dir = pathlib.Path(f"pipeline/data/problem_reports/report_{now}")
    report_dir.mkdir(parents=False, exist_ok=False)

    if problem_report.screenshot:
        screen = base64.b64decode(problem_report.screenshot.split(",")[1])
        (report_dir / "screenshot.png").write_bytes(screen)

    (report_dir / "message.txt").write_text(problem_report.problem_text)

    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": problem_report.problem_text}}]
    if problem_report.screenshot:
        blocks.append({
            "type": "image",
            "title": {"type": "plain_text", "text": "User screenshot:"},
            "block_id": "image4",
            "image_url": f"https://foodsight.ml4all.com/api/problems/report_{now}/screenshot.png",
            "alt_text": "screenshot from a foodsight user",
        })

    _post_to_slack({"blocks": blocks})
    return True


# ---------------------------------------------------------------------------
# Sign-ups
# ---------------------------------------------------------------------------

class SignupData(BaseModel):
    name: Optional[str] = None
    email: str
    phone: str
    password: str
    location: Optional[str] = None
    register_type: Optional[str] = None
    agree: bool


@app.post("/api/signup")
def post_signup(signup_data: SignupData):
    """Register a new user (hash password, notify via Slack)."""
    pw_hash = get_password_hash(signup_data.password)
    slack_text = (
        f"*** NEW SIGN-UP ***\n"
        f"name: {signup_data.name}\nemail: {signup_data.email}\n"
        f"phone: {signup_data.phone}\npassword: {pw_hash}\n"
        f"location: {signup_data.location}\nregister_type: {signup_data.register_type}\n"
        f"agree: {signup_data.agree}"
    )
    _post_to_slack({"blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": slack_text}}]})
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Order export
# ---------------------------------------------------------------------------

class OrderData(BaseModel):
    data: list
    option: str
    order_option: str


@app.post("/api/order")
def post_order(order_data: OrderData):
    """Generate an order file (xlsx or csv) from the current forecast data."""
    df = pd.DataFrame.from_records(data=order_data.data)
    df.rename(
        mapper={
            "id": "ID",
            "product": "Produkt",
            "tomorrow_order_qty": "Bestellung Morgen",
            "day_after_order_qty": "Bestellung Übermorgen",
            "next7_order_qty": "Bestellung nächste 7 Tage",
        },
        axis=1,
        inplace=True,
        errors="raise",
    )

    drop_map = {
        "tomorrow": ["day_after_order_range", "Bestellung Übermorgen", "next7_order_range", "Bestellung nächste 7 Tage", "tomorrow_order_range"],
        "day_after_tomorrow": ["tomorrow_order_range", "Bestellung Morgen", "next7_order_range", "Bestellung nächste 7 Tage", "day_after_order_range"],
        "next_seven_days": ["day_after_order_range", "Bestellung Übermorgen", "tomorrow_order_range", "Bestellung Morgen", "next7_order_range"],
    }
    if order_data.order_option in drop_map:
        df = df.drop(drop_map[order_data.order_option], axis=1)

    if order_data.option == "xlsx":
        path = "pipeline/data/Foodsight_Bestellung.xlsx"
        df.to_excel(path, index=False)
        return FileResponse(
            path=path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename="Foodsight_Bestellung.xlsx",
        )
    return df.to_csv(index=False)


# ---------------------------------------------------------------------------
# Static file mounts (must come after all routes)
# ---------------------------------------------------------------------------

app.mount("/api/problems", StaticFiles(directory="pipeline/data/problem_reports"), name="problems")
app.mount("/", StaticFiles(directory="client/public/"), name="static")
