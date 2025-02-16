from sqlalchemy import create_engine, Column, Integer, String, Float, JSON, Text
from sqlalchemy.types import TypeDecorator
import json
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

class JSONEncodedDict(TypeDecorator):
    impl = Text

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value)
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            return json.loads(value)
        return None

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
    categories = Column(JSONEncodedDict)
    address = Column(String)
    review_keywords = Column(JSONEncodedDict)
    link = Column(String)
    reviews_per_rating = Column(JSONEncodedDict)
    coordinates = Column(JSONEncodedDict)
    hours = Column(JSONEncodedDict)
    detailed_reviews = Column(Text)

# Create all tables
Base.metadata.create_all(engine)
