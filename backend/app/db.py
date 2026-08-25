import os
from sqlmodel import SQLModel, create_engine, Session

DB_FILE = os.environ.get("DB_FILE", "revenue_recovery.db")
DATABASE_URL = f"sqlite:///{DB_FILE}"

# Use connect_args to allow SQLite access across threads if needed
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}
)

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
