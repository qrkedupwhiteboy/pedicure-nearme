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
    name = Column(String(500))
    description = Column(String(10000))
    reviews = Column(Integer)
    rating = Column(Integer)
    website = Column(Text)
    phone = Column(String(50))
    featured_image = Column(Text)
    main_category = Column(String(100))
    categories = Column(Text)  # JSON array
    address = Column(Text)
    review_keywords = Column(Text)  # JSON data
    link = Column(Text)
    reviews_per_rating = Column(Text)  # JSON data
    coordinates = Column(Text)  # JSON data
    hours = Column(Text)  # JSON data
    detailed_reviews = Column(String(10000))  # JSON data

    def __repr__(self) -> str:
        """Return string representation of the listing."""
        return f"<PedicureListing(name='{self.business_name or ''}', city='{self.city or ''}')>"

# Database connection
engine = create_engine(os.getenv('DATABASE_URL'))
Session = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)
