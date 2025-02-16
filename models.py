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
    city = Column(String(100))
    state = Column(String(10))  # Increased from 2 to handle potential longer state codes
    zip_code = Column(String(10))
    review_keywords = Column(Text)  # JSON data
    link = Column(Text)
    reviews_per_rating = Column(Text)  # JSON data
    coordinates = Column(Text)  # JSON data
    hours = Column(Text)  # JSON data
    detailed_reviews = Column(String(10000))  # JSON data

    @staticmethod
    def parse_address(address):
        """Parse address string into components."""
        if not address:
            return None, None, None
        
        try:
            # Split address by commas and clean up whitespace
            parts = [part.strip() for part in address.split(',')]
            
            if len(parts) >= 2:
                # Last part typically contains state and zip
                state_zip = parts[-1].split()
                if len(state_zip) >= 2:
                    state = state_zip[0]
                    zip_code = state_zip[1]
                else:
                    state = state_zip[0] if state_zip else None
                    zip_code = None
                
                # Second to last part is typically the city
                city = parts[-2]
                
                return city, state, zip_code
        except:
            return None, None, None
        
        return None, None, None

    def __repr__(self) -> str:
        """Return string representation of the listing."""
        return f"<PedicureListing(name='{self.name or ''}', city='{self.city or ''}')>"

# Database connection
engine = create_engine(os.getenv('DATABASE_URL'))
Session = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)
