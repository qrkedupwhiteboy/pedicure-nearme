from flask import Flask, render_template, request
from models import Session, PedicureListing
from sqlalchemy import text, func
import os
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import folium
from sqlalchemy import or_

# State code to full name mapping
STATE_NAMES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California',
    'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia',
    'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa',
    'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi', 'MO': 'Missouri',
    'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey',
    'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio',
    'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont',
    'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming'
}

load_dotenv()

app = Flask(__name__)

@app.route('/')
def home():
    session = Session()
    try:
        # Query cities with their listing counts
        city_counts = session.query(
            PedicureListing.state,
            PedicureListing.city,
            func.count(PedicureListing.id).label('count')
        ).group_by(
            PedicureListing.state,
            PedicureListing.city
        ).having(
            PedicureListing.city.isnot(None)
        ).order_by(
            PedicureListing.state,
            text('count DESC')
        ).all()

        # Organize into state-city dictionary with top 5 cities per state
        states_cities = {}
        for state, city, count in city_counts:
            if state and len(state) == 2:  # Only include valid state codes
                state_name = STATE_NAMES.get(state)
                if state_name:
                    if state not in states_cities:
                        states_cities[state] = {
                            'name': state_name,
                            'top_cities': [], 
                            'total_cities': 0
                        }
                    if len(states_cities[state]['top_cities']) < 5:
                        states_cities[state]['top_cities'].append(city)
                    states_cities[state]['total_cities'] += 1

        return render_template('index.html', states_cities=states_cities)
    finally:
        session.close()

@app.route('/search')
def search():
    """Handle search requests for pedicure listings."""
    session = Session()
    try:
        # Get search parameters with proper type hints
        location: str = request.args.get('location', '').strip()
        state: str = request.args.get('state', '').upper()
        min_rating: float | None = request.args.get('min_rating', type=float)
        price_level: str | None = request.args.get('price_level')
        sort_by: str = request.args.get('sort', 'rating')  # Default sort by rating
        page: int = request.args.get('page', 1, type=int)
        per_page: int = 12  # Number of listings per page
        
        # Initialize base query
        query = session.query(PedicureListing)
        
        # Initialize geocoder and handle location-based filtering
        try:
            geolocator = Nominatim(user_agent="pedicure_finder")
            
            if location:
                # Check if it's a ZIP code
                if location.isdigit() and len(location) == 5:
                    geo_location = geolocator.geocode(f"{location}, USA")
                    if geo_location:
                        # Search within ~5 mile radius (0.07 degrees)
                        radius = 0.07
                        query = query.filter(
                            PedicureListing.latitude.between(geo_location.latitude - radius, geo_location.latitude + radius),
                            PedicureListing.longitude.between(geo_location.longitude - radius, geo_location.longitude + radius)
                        )
                else:
                    # Assume it's a city name
                    city = location.split('-')[0].strip().title()
                    query = query.filter(PedicureListing.city == city)
            elif state:
                query = query.filter(PedicureListing.state == state)
        except GeocoderTimedOut:
            # Handle geocoding timeout gracefully
            if location and not location.isdigit():
                city = location.split('-')[0].strip().title()
                query = query.filter(PedicureListing.city == city)
        
        # Apply additional filters
        if min_rating:
            query = query.filter(PedicureListing.rating >= min_rating)
        if price_level:
            query = query.filter(PedicureListing.price_level == price_level)
            
        # Apply sorting
        if sort_by == 'rating':
            query = query.order_by(PedicureListing.rating.desc(), PedicureListing.reviews.desc())
        elif sort_by == 'reviews':
            query = query.order_by(PedicureListing.reviews.desc())
        elif sort_by == 'name':
            query = query.order_by(PedicureListing.business_name)
        
        # Get total count for pagination
        total = query.count()
        
        # Apply pagination
        listings = query.offset((page - 1) * per_page).limit(per_page).all()
        
        # Create map
        try:
            if listings:
                valid_coords = [(l.latitude, l.longitude) 
                               for l in listings 
                               if l.latitude is not None and l.longitude is not None]
                if valid_coords:
                    map_center = [
                        sum(lat for lat, _ in valid_coords) / len(valid_coords),
                        sum(lon for _, lon in valid_coords) / len(valid_coords)
                    ]
                else:
                    map_center = [39.8283, -98.5795]  # Default to center of USA
                m = folium.Map(location=map_center, zoom_start=12)
                
                # Add markers for each listing
                for listing in listings:
                    if listing.latitude and listing.longitude:
                        folium.Marker(
                            [listing.latitude, listing.longitude],
                            popup=f"<b>{listing.business_name}</b><br>Rating: {listing.rating}★<br>{listing.address}",
                            icon=folium.Icon(color='red', icon='info-sign')
                        ).add_to(m)
                
                # Save map to template directory
                m.save('templates/map.html')
        except Exception as e:
            print(f"Error creating map: {str(e)}")
        
        location_name = location.title() if location else STATE_NAMES.get(state) or state
        
        return render_template('listings.html', 
                             listings=listings,
                             location=location_name,
                             is_city=bool(location and not location.isdigit()),
                             current_page=page,
                             total_pages=(total + per_page - 1) // per_page,
                             total_listings=total,
                             filters={
                                 'min_rating': min_rating,
                                 'price_level': price_level,
                                 'sort_by': sort_by
                             })
    finally:
        session.close()

@app.route('/data')
def view_data():
    session = Session()
    try:
        listings = session.query(PedicureListing).limit(100).all()
        # Add debug print
        if listings:
            print(f"First listing: {listings[0].__dict__}")
        else:
            print("No listings found")
        return render_template('data.html', listings=listings)
    finally:
        session.close()

if __name__ == '__main__':
    app.run(debug=True)
