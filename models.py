from sqlalchemy import create_engine, Column, Integer, String, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(verbose=True)

# Verify DATABASE_URL is loaded
database_url = os.getenv('DATABASE_URL')
if not database_url:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(current_dir, '.env')
    raise ValueError(f"DATABASE_URL environment variable is not set. \nChecking for .env file at: {env_path}\nMake sure the .env file exists and contains: DATABASE_URL=postgresql://emrsn@localhost:5432/pedicure_directory")

Base = declarative_base()

class PedicureListing(Base):
    __tablename__ = 'pedicure_listings'

    id = Column(Integer, primary_key=True)
    business_name = Column(String(255))
    address = Column(String(255))
    city = Column(String(100))
    state = Column(String(2))
    zip_code = Column(String(10))
    latitude = Column(Float)
    longitude = Column(Float)
    rating = Column(Float)
    total_ratings = Column(Integer)
    phone = Column(String(20))
    website = Column(String(255))
    business_hours = Column(Text)
    price_level = Column(String(10))

    def __repr__(self):
        return f"<PedicureListing(name='{self.business_name}', city='{self.city}')>"

# Database connection
engine = create_engine(os.getenv('DATABASE_URL'))
Session = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)
