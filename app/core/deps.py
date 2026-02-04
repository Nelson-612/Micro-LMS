from app.db.session import SessionLocal

# every request that needs DB will get a fresh session, and it will always close.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
