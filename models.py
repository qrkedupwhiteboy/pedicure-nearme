from sqlalchemy import create_engine, Column, Integer, String, Float, Text
from typing import Optional, Tuple
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

    # Valid US state codes
    US_STATES = {
        'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
        'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
        'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
        'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
        'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
        'DC'  # Including District of Columbia
    }

    @staticmethod
    def parse_address(address: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Parse address string into components.
        Returns (city, state, zip_code) tuple, with None for invalid/missing components.
        Only returns valid US state codes.
        """
        if not address:
            return None, None, None
        
        try:
            # Split address by commas and clean up whitespace
            parts = [part.strip() for part in address.split(',')]
            
            if len(parts) >= 2:
                # Last part typically contains state and zip
                state_zip = parts[-1].split()
                if len(state_zip) >= 2:
                    state = state_zip[0].upper()
                    zip_code = state_zip[1]
                else:
                    state = state_zip[0].upper() if state_zip else None
                    zip_code = None
                
                # Validate state code
                if state not in PedicureListing.US_STATES:
                    return None, None, None
                
                # Second to last part is typically the city
                city = parts[-2]
                
                # Basic zip code validation
                if zip_code and not (zip_code.isdigit() and len(zip_code) == 5):
                    zip_code = None
                
                return city, state, zip_code
        except:
            return None, None, None
        
        return None, None, None

    def get_url_slug(self) -> str:
        """Generate URL-safe slug from name and zipcode"""
        if not self.name or not self.zip_code:
            return str(self.id)  # Fallback to ID if missing data
        name_slug = self.name.lower().replace(' ', '-')
        # Remove any non-alphanumeric chars except hyphens
        name_slug = ''.join(c for c in name_slug if c.isalnum() or c == '-')
        return f"{name_slug}-{self.zip_code}"

    def __repr__(self) -> str:
        """Return string representation of the listing."""
        return f"<PedicureListing(name='{self.name or ''}', city='{self.city or ''}')>"

# Database connection
engine = create_engine(os.getenv('DATABASE_URL'))
Session = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)
