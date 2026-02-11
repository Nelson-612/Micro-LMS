from datetime import timedelta

# DEV ONLY: hardcoded secret. Later we will load from env vars.
SECRET_KEY = "change-me-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE = timedelta(minutes=60)
