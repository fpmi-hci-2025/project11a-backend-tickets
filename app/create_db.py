from sqlalchemy import create_engine
from main import Base, engine


def create():
    Base.metadata.create_all(bind=engine)
    print("Database and tables created (SQLite at ./train_booking.db)")

if __name__ == "__main__":
    create()
