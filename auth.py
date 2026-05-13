import os
from dotenv import load_dotenv
from supabase import create_client, Client
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import hashlib

load_dotenv()

ACCESS_TOKEN: str = os.environ.get("ACCESS_TOKEN")

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """
    Validates the bearer token against the 'tokens' table in Supabase.
    Raises HTTP 401 if the token is missing or not found in the database.
    """
    token = credentials.credentials

    if not token:
        raise HTTPException(status_code=500, detail="Token is invalid")

    response = token == ACCESS_TOKEN

    if not response:
        raise HTTPException(status_code=401, detail="Invalid or unauthorized token")
