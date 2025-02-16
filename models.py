from sqlalchemy import create_engine, Column, Integer, String, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
from sqlalchemy.dialects.postgresql import JSONB


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
    business_name = Column(String(500))
    address = Column(String(500))
    city = Column(String(100))
    state = Column(String(100))
    zip_code = Column(String(10))
    coordinates = Column(JSONB)
    rating = Column(Float)
    total_ratings = Column(Integer)
    review_keywords = Column(JSONB)
    link = Column(Text)
    phone = Column(String(50))
    website = Column(Text)
    description = Column(Text)
    reviews = Column(Integer)
    featured_image = Column(Text)
    main_category = Column(String(100))
    categories = Column(JSONB)  # JSON array of category strings
    workday_timing = Column(JSONB)
    closed_on = Column(JSONB)
    reviews_per_rating = Column(JSONB)  # JSON object with rating counts
    hours = Column(JSONB)  # JSON array of daily hours objects
    detailed_reviews = Column(JSONB)  # JSON array of review objects
    business_hours = Column(JSONB)
    price_level = Column(String(10))

    def __repr__(self) -> str:
        """Return string representation of the listing."""
        return f"<PedicureListing(name='{self.business_name or ''}', city='{self.city or ''}')>"

# Database connection
engine = create_engine(os.getenv('DATABASE_URL'))
Session = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)
