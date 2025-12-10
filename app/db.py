from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Use the standardized URL variable name
SQLALCHEMY_DATABASE_URL = "sqlite:///./attendance.db"

# Create the engine to connect to the database
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

# Create a SessionLocal class for handling database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create the Base class for declaring models
Base = declarative_base()