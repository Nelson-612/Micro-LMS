from datetime import timedelta

# DEV ONLY: hardcoded secret. Later we will load from env vars.
SECRET_KEY = "change-me-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE = timedelta(minutes=60)

# Late policy
GRACE_PERIOD_MINUTES = 10  # submissions within 10 mins after due are not late
LATE_PENALTY_PER_DAY = 0.10  # 10% per day late
LATE_PENALTY_MAX = 0.50  # max 50% total deduction
