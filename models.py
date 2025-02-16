from sqlalchemy import create_engine, Column, Integer, String, Float, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()
engine = create_engine(os.getenv('DATABASE_URL'))
Session = sessionmaker(bind=engine)

class Business(Base):
    __tablename__ = 'businesses'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(Text)
    reviews = Column(Float)
    rating = Column(Float)
    website = Column(String)
    phone = Column(String)
    featured_image = Column(String)
    main_category = Column(String)
    categories = Column(JSON)
    address = Column(String)
    review_keywords = Column(JSON)
    link = Column(String)
    reviews_per_rating = Column(JSON)
    coordinates = Column(JSON)
    hours = Column(JSON)
    detailed_reviews = Column(Text)

# Create all tables
Base.metadata.create_all(engine)
