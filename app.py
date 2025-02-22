from flask import Flask, render_template, request, abort, jsonify
from models import Session, PedicureListing
from sqlalchemy import text, func
import os
from dotenv import load_dotenv
import json
from typing import Dict, Optional
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import folium
from folium import Popup
import json
from sqlalchemy import or_
import requests
from requests.structures import CaseInsensitiveDict
from functools import lru_cache

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

GEOAPIFY_API_KEY = os.getenv('GEOAPIFY_API_KEY')
REVERSE_GEOCODE_KEY = os.getenv('REVERSE_GEOCODE_KEY')
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

        return render_template('index.html', 
                             states_cities=states_cities)
    finally:
        session.close()

@app.route('/get_geoapify_location')
def get_geoapify_location():
    """Get basic location data from IP"""
    try:
        url = f"https://api.geoapify.com/v1/ipinfo?apiKey={GEOAPIFY_API_KEY}"
        headers = {
            "Accept": "application/json"
        }
        response = requests.get(url, headers=headers)
        
        app.logger.info(f"Geoapify API status code: {response.status_code}")
        
        if not response.ok:
            app.logger.error(f"Geoapify API error: Status {response.status_code}")
            return jsonify({'error': 'Could not detect location'}), response.status_code
            
        location_data = response.json()
        if not location_data:
            app.logger.error("Empty response from Geoapify")
            return jsonify({'error': 'Empty response from Geoapify'}), 500

        app.logger.info(f"Location data: {location_data}")
        return jsonify(location_data)
    except Exception as e:
        app.logger.error(f"Geoapify location error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/nearby_locations', methods=['GET'])
def get_nearby_locations():
    """Get nearby zipcodes with pedicure listings"""
    try:
        lat = request.args.get('lat')
        lon = request.args.get('lon')
        
        if not lat or not lon:
            return jsonify({'error': 'Missing latitude or longitude'}), 400
            
        # Convert to float
        lat = float(lat)
        lon = float(lon)
        
        session = Session()
        try:
            # Find locations within rough radius using bounding box
            # 1 degree lat/lon ≈ 111km at equator, adjust as needed
            radius = 0.5  # roughly 50km
            
            # Extract latitude and longitude from JSON coordinates
            nearby = session.query(
                PedicureListing.city,
                PedicureListing.state,
                PedicureListing.zip_code,
                func.count(PedicureListing.id).label('listing_count')
            ).filter(
                text("(coordinates->>'latitude')::float BETWEEN :lat_min AND :lat_max"),
                text("(coordinates->>'longitude')::float BETWEEN :lon_min AND :lon_max"),
                PedicureListing.zip_code.isnot(None)
            ).params(
                lat_min=lat - radius,
                lat_max=lat + radius,
                lon_min=lon - radius,
                lon_max=lon + radius
            ).group_by(
                PedicureListing.city,
                PedicureListing.state,
                PedicureListing.zip_code
            ).order_by(
                text('listing_count DESC')
            ).limit(10).all()
            
            locations = [
                {
                    'city': loc.city,
                    'state': loc.state,
                    'zipcode': loc.zip_code,
                    'listing_count': loc.listing_count
                }
                for loc in nearby
            ]
            
            return jsonify({'nearby_locations': locations})
            
        finally:
            session.close()
            
    except Exception as e:
        app.logger.error(f"Nearby locations error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/map/<zipcode>')
def map_view(zipcode):
    """Display a map of pedicure listings for a given zipcode"""
    session = Session()
    try:
        # Get filter parameters
        min_rating = request.args.get('rating', type=float)
        min_reviews = request.args.get('reviews', type=int)
        sort_by = request.args.get('sort', 'rating')  # Default sort by rating
        
        # Build base query
        query = session.query(PedicureListing).filter(
            PedicureListing.zip_code == zipcode,
            PedicureListing.coordinates.isnot(None)
        )
        
        # Apply filters
        if min_rating:
            query = query.filter(PedicureListing.rating >= min_rating)
        if min_reviews:
            query = query.filter(PedicureListing.reviews >= min_reviews)
            
        # Get user coordinates for distance calculation if provided
        user_lat = request.args.get('user_lat', type=float)
        user_lon = request.args.get('user_lon', type=float)

        # Apply sorting
        if sort_by == 'rating':
            query = query.order_by(PedicureListing.rating.desc())
        elif sort_by == 'reviews':
            query = query.order_by(PedicureListing.reviews.desc())
        # Note: Distance sorting happens in memory after query
            
        listings = query.all()
        
        if not listings:
            abort(404)
            
        # Create map centered on the first listing
        first_coords = listings[0].coordinates
        map_center = [first_coords['latitude'], first_coords['longitude']]
        m = folium.Map(location=map_center, zoom_start=13)
        
        # Add markers for each listing
        for listing in listings:
            coords = listing.coordinates
            popup_html = f"""
                <div class='listing-popup'>
                    <h3>{listing.name}</h3>
                    <p>{listing.address}</p>
                    <p class='rating'>Rating: {listing.rating}/5 ({listing.reviews} reviews)</p>
                    <p>{listing.phone}</p>
                    <a href='{listing.website}' target='_blank'>Visit Website</a>
                </div>
            """
            
            folium.Marker(
                location=[coords['latitude'], coords['longitude']],
                popup=Popup(popup_html, max_width=300),
                icon=folium.Icon(color='blue', icon='info-sign')
            ).add_to(m)
            
        return render_template('map_view.html', map_html=m._repr_html_(), listings=listings)
    finally:
        session.close()

@app.route('/cities-with-pedicures-in/<state>')
def state_listings(state):
    """Display pedicure listings for a specific state"""
    session = Session()
    try:
        # Get state name from code
        state_name = STATE_NAMES.get(state.upper())
        if not state_name:
            abort(404)
            
        # Query cities and their listing counts for the state
        cities = session.query(
            PedicureListing.city,
            func.count(PedicureListing.id).label('listing_count')
        ).filter(
            func.upper(PedicureListing.state) == state.upper(),
            PedicureListing.city.isnot(None)
        ).group_by(
            PedicureListing.city
        ).order_by(
            PedicureListing.city
        ).all()
        
        if not cities:
            abort(404)
            
        # Format city data
        city_data = [
            {'city': city[0], 'listing_count': city[1]}
            for city in cities
        ]
        
        return render_template('state_listings.html',
                             state_code=state.upper(),
                             state_name=state_name,
                             cities=city_data)
    finally:
        session.close()

@app.route('/pedicures-in/<city>')
def city_listings(city):
    """Display pedicure listings for a specific city"""
    session = Session()
    try:
        # Parse city name to handle URL format (e.g., "new-york" -> "New York")
        city_name = " ".join(word.capitalize() for word in city.split('-'))
        
        # Query listings for the city
        listings = session.query(PedicureListing).filter(
            func.lower(PedicureListing.city) == func.lower(city_name),
            PedicureListing.coordinates.isnot(None)  # Ensure we have coordinates
        ).order_by(
            PedicureListing.rating.desc()
        ).all()
        
        if not listings:
            abort(404)
            
        # Get state from first listing
        state = listings[0].state
        
        return render_template('city_listings.html',
                             city=city_name,
                             state=state,
                             listings=listings)
    finally:
        session.close()

def parse_hours(hours_text: Optional[str]) -> Dict[str, str]:
    """Parse hours from JSON text into a dictionary of day -> hours string"""
    if not hours_text:
        return {
            'Monday': 'Not specified',
            'Tuesday': 'Not specified', 
            'Wednesday': 'Not specified',
            'Thursday': 'Not specified',
            'Friday': 'Not specified',
            'Saturday': 'Not specified',
            'Sunday': 'Not specified'
        }
    
    try:
        hours_dict = json.loads(hours_text)
        # Ensure all days are present
        default_hours = {
            'Monday': 'CLOSED',
            'Tuesday': 'CLOSED',
            'Wednesday': 'CLOSED', 
            'Thursday': 'CLOSED',
            'Friday': 'CLOSED',
            'Saturday': 'CLOSED',
            'Sunday': 'CLOSED'
        }
        default_hours.update(hours_dict)
        return default_hours
    except json.JSONDecodeError:
        # Return default hours if JSON parsing fails
        return {
            'Monday': 'Error parsing hours',
            'Tuesday': 'Error parsing hours',
            'Wednesday': 'Error parsing hours',
            'Thursday': 'Error parsing hours', 
            'Friday': 'Error parsing hours',
            'Saturday': 'Error parsing hours',
            'Sunday': 'Error parsing hours'
        }

@app.route('/listing/<int:listing_id>')
def listing_page(listing_id):
    """Display a single pedicure listing"""
    session = Session()
    try:
        # Get the main listing
        listing = session.query(PedicureListing).get(listing_id)
        if not listing:
            abort(404)
            
        # Get nearby listings in same zipcode, ordered by rating
        nearby_listings = session.query(PedicureListing).filter(
            PedicureListing.zip_code == listing.zip_code,
            PedicureListing.id != listing_id,
            PedicureListing.coordinates.isnot(None)
        ).order_by(
            PedicureListing.rating.desc()
        ).limit(2).all()
        
        # Get cities in the same state that have listings
        cities_in_state = session.query(
            PedicureListing.city
        ).filter(
            PedicureListing.state == listing.state,
            PedicureListing.city.isnot(None)
        ).group_by(
            PedicureListing.city
        ).order_by(
            PedicureListing.city
        ).all()
        
        cities_in_state = [city[0] for city in cities_in_state]  # Unpack from tuples
        
        return render_template('listing.html', 
                             listing=listing,
                             nearby_listings=nearby_listings,
                             cities_in_state=cities_in_state,
                             parse_hours=parse_hours)
    finally:
        session.close()

@app.route('/get_zipcode', methods=['GET'])
def get_zipcode():
    """Get zipcode from latitude and longitude"""
    try:
        lat = request.args.get('lat')
        lon = request.args.get('lon')
        
        app.logger.info(f"Received coordinates: lat={lat}, lon={lon}")
        
        if not lat or not lon:
            return jsonify({'error': 'Missing latitude or longitude'}), 400
            
        # Call reverse geocoding API
        url = f"https://api.geoapify.com/v1/geocode/reverse?lat={lat}&lon={lon}&apiKey={REVERSE_GEOCODE_KEY}"
        headers = {
            "Accept": "application/json"
        }
        response = requests.get(url, headers=headers)
        
        # Log the actual URL being called for debugging
        app.logger.debug(f"Calling URL: {response.url}")
        app.logger.info(f"Geoapify raw response: {response.text}")
        
        if not response.ok:
            app.logger.error(f"Reverse geocoding failed: {response.status_code}")
            return jsonify({'error': 'Reverse geocoding failed'}), response.status_code
            
        data = response.json()
        app.logger.debug(f"Reverse geocoding response: {data}")
        
        if data and 'features' in data and len(data['features']) > 0:
            properties = data['features'][0]['properties']
            if 'postcode' in properties:
                app.logger.info(f"Found zipcode: {properties['postcode']}")
                return jsonify({'zipcode': properties['postcode']})
            else:
                app.logger.warning("No postcode found in properties")
                return jsonify({'error': 'No zipcode found'}), 404
        else:
            app.logger.warning("No features found in response")
            return jsonify({'error': 'No location data found'}), 404
            
    except Exception as e:
        app.logger.error(f"Zipcode lookup error: {str(e)}")
        return jsonify({'error': str(e)}), 500

