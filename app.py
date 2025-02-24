from flask import Flask, render_template, request, abort, jsonify, Response
from models import Session, PedicureListing
from sqlalchemy import text, func
import os
from dotenv import load_dotenv
import json
from typing import Dict, Optional, List
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

@app.route('/map/<location>')
def map_view(location):
    """Display a map of pedicure listings for a given location (zipcode or city)"""
    session = Session()
    try:
        # Get filter parameters
        min_rating = request.args.get('rating', type=float)
        min_reviews = request.args.get('reviews', type=int)
        sort_by = request.args.get('sort', 'rating')  # Default sort by rating
        
        # Build base query
        query = session.query(PedicureListing).filter(
            PedicureListing.coordinates.isnot(None)
        )

        # Check if location is a zipcode (5 digits) or city name
        if location.isdigit() and len(location) == 5:
            query = query.filter(PedicureListing.zip_code == location)
        else:
            # Convert URL format (e.g., "new-york") to proper city name ("New York")
            city_name = " ".join(word.capitalize() for word in location.split('-'))
            query = query.filter(func.lower(PedicureListing.city) == func.lower(city_name))
        
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

@app.route('/about')
def about_page():
    return render_template('about.html')

@app.route('/contact')
def contact_page():
    return render_template('contact.html')

@app.route('/sitemap.xml')
def sitemap():
    """Generate sitemap.xml"""
    session = Session()
    try:
        # Get all cities with listings
        cities = session.query(
            PedicureListing.city,
            PedicureListing.state
        ).filter(
            PedicureListing.city.isnot(None),
            PedicureListing.state.isnot(None)
        ).distinct().all()

        # Get all listings
        listings = session.query(PedicureListing).all()

        # Build sitemap XML
        xml = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
        
        # Add static pages
        base_url = request.url_root.rstrip('/')
        static_paths = ['', '/about', '/contact']
        for path in static_paths:
            xml.append(f'  <url><loc>{base_url}{path}</loc></url>')

        # Add state pages
        for state_code in STATE_NAMES.keys():
            xml.append(f'  <url><loc>{base_url}/cities-with-pedicures-in/{state_code.lower()}</loc></url>')

        # Add city pages
        for city, state in cities:
            if city and state:
                city_url = city.lower().replace(' ', '-')
                xml.append(f'  <url><loc>{base_url}/pedicures-in/{city_url}</loc></url>')

        # Add individual listing pages
        for listing in listings:
            xml.append(f'  <url><loc>{base_url}/listing/{listing.id}</loc></url>')

        xml.append('</urlset>')
        
        return Response('\n'.join(xml), mimetype='application/xml')
    finally:
        session.close()

@app.route('/submit_contact', methods=['POST'])
def submit_contact():
    """Handle contact form submission"""
    try:
        # Get form data
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')
        
        # Here you would typically:
        # 1. Validate the data
        # 2. Send an email or store in database
        # 3. Send confirmation email to user
        
        return jsonify({'success': True, 'message': 'Thank you for your message. We will respond shortly.'})
    except Exception as e:
        app.logger.error(f"Contact form error: {str(e)}")
        return jsonify({'error': 'Failed to send message'}), 500

def parse_categories(categories: Optional[List[str]]) -> List[str]:
    """Convert categories list into list of strings"""
    if not categories:
        return []
    
    try:
        # Ensure each category is converted to string
        return [str(cat) for cat in categories]
    except (TypeError, ValueError):
        return []

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
        hours_array = json.loads(hours_text)
        # Convert array of day objects to dictionary
        hours_dict = {}
        for day_obj in hours_array:
            day = day_obj['day']
            times = day_obj['times']
            # Join multiple times with commas if present
            hours_dict[day] = ', '.join(times)
            
        # Ensure all days are present
        default_hours = {
            'Monday': 'Not Found',
            'Tuesday': 'Not Found',
            'Wednesday': 'Not Found', 
            'Thursday': 'Not Found',
            'Friday': 'Not Found',
            'Saturday': 'Not Found',
            'Sunday': 'Not Found'
        }
        default_hours.update(hours_dict)
        return default_hours
    except (json.JSONDecodeError, KeyError, TypeError):
        # Return default hours if JSON parsing fails or required fields missing
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
        
        # Parse hours once for the template
        hours_data = parse_hours(listing.hours)
        
        return render_template('listing.html', 
                             listing=listing,
                             nearby_listings=nearby_listings,
                             cities_in_state=cities_in_state,
                             hours_data=hours_data,
                             parse_hours=parse_hours,
                             parse_categories=parse_categories)
    finally:
        session.close()

@app.route('/search_locations', methods=['GET'])
def search_locations():
    """Search locations (zipcodes or cities) based on input"""
    try:
        query = request.args.get('q', '')
        if not query or len(query) < 2:
            return jsonify([])
            
        session = Session()
        try:
            # Search for both zipcodes and cities
            results = session.query(
                PedicureListing.zip_code,
                PedicureListing.city,
                PedicureListing.state,
                func.count(PedicureListing.id).label('listing_count')
            ).filter(
                or_(
                    PedicureListing.zip_code.ilike(f'{query}%'),
                    PedicureListing.city.ilike(f'{query}%')
                )
            ).group_by(
                PedicureListing.zip_code,
                PedicureListing.city,
                PedicureListing.state
            ).order_by(
                func.count(PedicureListing.id).desc()
            ).limit(8).all()
            
            return jsonify([{
                'zipcode': r.zip_code,
                'city': r.city,
                'state': r.state,
                'listing_count': r.listing_count,
                'type': 'zipcode' if query in str(r.zip_code) else 'city'
            } for r in results])
            
        finally:
            session.close()
            
    except Exception as e:
        app.logger.error(f"Zipcode search error: {str(e)}")
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

@app.context_processor                                                                                    
def utility_processor():                                                                                  
     return {                                                                                              
         'STATE_NAMES': STATE_NAMES                                                                        
     }                                                                                                     
                          

