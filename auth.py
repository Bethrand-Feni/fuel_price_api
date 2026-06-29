import os
import secrets

from dotenv import load_dotenv
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

load_dotenv()

ACCESS_TOKEN: str | None = os.environ.get("ACCESS_TOKEN")

security = HTTPBearer(auto_error=False)


def verify_token(credentials: HTTPAuthorizationCredentials | None = Security(security)):
    token = credentials.credentials if credentials else None

    if not ACCESS_TOKEN or not token:
        raise HTTPException(status_code=401, detail="Invalid or unauthorized token")

    if not secrets.compare_digest(token, ACCESS_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid or unauthorized token")
