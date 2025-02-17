from flask import Flask, render_template, request, abort, jsonify
from models import Session, PedicureListing
from sqlalchemy import text, func
import os
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import folium
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
        url = "https://api.geoapify.com/v1/geocode/reverse"
        params = {
            "lat": lat,
            "lon": lon,
            "apiKey": REVERSE_GEOCODE_KEY
        }
        headers = CaseInsensitiveDict()
        headers["Accept"] = "application/json"
        
        response = requests.get(url, params=params, headers=headers)
        
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

