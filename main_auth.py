from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

import dotenv
import os
import toml

#TODO: Allow user to change expiration time for tokens in UI between 1 day and 6 months

# to get a __SECRET_KEY run:
# openssl rand -hex 32
# load env vars
dotenv.load_dotenv('.env')

# load customer specific config
config = toml.load('pipeline/data/customer.toml')

__SECRET_KEY = os.environ.get('SECRET_KEY')
__ALGORITHM = os.environ.get('ALGORITHM')
ACCESS_TOKEN_EXPIRE_MINUTES = config['base']['login_valid_minutes'] #60*18

__users_db = config['users']
#print(__users_db)

# used to be handed to the client for authenticated requests
class Token(BaseModel):
    access_token: str
    token_type: str
    expires: str

# used to extract username from token we received from the client
class TokenData(BaseModel):
    username: Optional[str] = None


class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None

# used to retrieve the hashed password of the user from db 
class UserInDB(User):
    hashed_password: str

# used to hash and verify passwords
__pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# we use the OAuth2 "Password with Bearer"-flow
__oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/token")

# does the plaintext-password match the hashed version on file?
def __verify_password(plain_password, hashed_password):
    return __pwd_context.verify(plain_password, hashed_password)

# hashes a password
def __get_password_hash(password):
    return __pwd_context.hash(password)

# retrieve a user's hashed password from db (could retrieve more)
def __get_user(db, username: str):
    result = [e for e in db if e['username']==username]
    if len(result) > 0:
        #print(result)
        return UserInDB(**result[0])

# * check if password is correct. If true return users hashed password
def authenticate_user(username: str, password: str):
    user = __get_user(__users_db, username)
    if not user:
        return False
    if not __verify_password(password, user.hashed_password):
        return False
    return user

# * relatively generic method to generate a jwt-token from a dict
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, __SECRET_KEY, algorithm=__ALGORITHM)
    return encoded_jwt, expire

# validate a token received from client and if successful return users hashed password
async def __get_current_user(token: str = Depends(__oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, __SECRET_KEY, algorithms=[__ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = __get_user(__users_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

# * wrapper around get_current_user that checks if the user is inactve
async def get_current_active_user(current_user: User = Depends(__get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

