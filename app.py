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
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_ip_info(ip):
    """Cache IP geolocation results"""
    try:
        response = requests.get(f"https://ipapi.co/{ip}/json/")
        return response.json()
    except:
        return None

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
        format: str = request.args.get('format', 'html')  # New parameter for JSON/HTML response
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
                
                # Add markers for each listing with enhanced popups
                for listing in listings:
                    if listing.latitude and listing.longitude:
                        popup_html = f"""
                            <div style="width: 200px;">
                                <h3 style="color: #1c79ca; margin-bottom: 8px;">{listing.business_name}</h3>
                                <p style="margin: 4px 0;">Rating: {'★' * int(listing.rating)}{' ☆' * (5-int(listing.rating))} ({listing.rating})</p>
                                <p style="margin: 4px 0; color: #666;">{listing.address}</p>
                                {f'<p style="margin: 4px 0; color: #4caf50;">{listing.price_level}</p>' if listing.price_level else ''}
                                {f'<p style="margin: 4px 0;"><a href="tel:{listing.phone}" style="color: #1c79ca;">{listing.phone}</a></p>' if listing.phone else ''}
                            </div>
                        """
                        folium.Marker(
                            [listing.latitude, listing.longitude],
                            popup=folium.Popup(popup_html, max_width=300),
                            icon=folium.Icon(color='red', icon='info-sign')
                        ).add_to(m)
                
                # Add location search box
                m.add_child(folium.LatLngPopup())
                
                # Get the map HTML directly
                map_html = m._repr_html_()
        except Exception as e:
            print(f"Error creating map: {str(e)}")
            map_html = ""
        
        location_name = location.title() if location else STATE_NAMES.get(state) or state
        
        if format == 'json':
            return {
                'listings': [{
                    'id': l.id,
                    'business_name': l.business_name,
                    'address': l.address,
                    'latitude': l.latitude,
                    'longitude': l.longitude,
                    'rating': l.rating,
                    'reviews': l.reviews,
                    'phone': l.phone
                } for l in listings],
                'total': total,
                'page': page,
                'pages': (total + per_page - 1) // per_page
            }
        
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

@app.route('/listing/<int:listing_id>')
def listing_detail(listing_id):
    """Display detailed information for a specific listing."""
    session = Session()
    try:
        listing = session.query(PedicureListing).filter(PedicureListing.id == listing_id).first()
        if listing is None:
            abort(404)
        return render_template('listing.html', listing=listing)
    finally:
        session.close()

@app.route('/get_ip_location')
def get_ip_location():
    """Get location from IP address and nearby locations"""
    try:
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if client_ip == '127.0.0.1':
            # For local development, return a default location with nearby areas
            return jsonify({
                'zipcode': '10001',
                'city': 'New York',
                'state': 'NY',
                'nearby_locations': [
                    {'city': 'New York', 'state': 'NY', 'zipcode': '10001'},
                    {'city': 'Brooklyn', 'state': 'NY', 'zipcode': '11201'},
                    {'city': 'Queens', 'state': 'NY', 'zipcode': '11101'},
                    {'city': 'Jersey City', 'state': 'NJ', 'zipcode': '07302'},
                    {'city': 'Hoboken', 'state': 'NJ', 'zipcode': '07030'}
                ]
            })
            
        location_data = get_ip_info(client_ip)
        if location_data and location_data.get('postal'):
            # Query database for nearby locations
            session = Session()
            try:
                nearby = session.query(
                    PedicureListing.city,
                    PedicureListing.state,
                    PedicureListing.zipcode
                ).filter(
                    PedicureListing.latitude.between(
                        location_data.get('latitude') - 0.5,
                        location_data.get('latitude') + 0.5
                    ),
                    PedicureListing.longitude.between(
                        location_data.get('longitude') - 0.5,
                        location_data.get('longitude') + 0.5
                    )
                ).distinct().limit(5).all()
                
                return jsonify({
                    'zipcode': location_data['postal'],
                    'city': location_data.get('city'),
                    'state': location_data.get('region_code'),
                    'nearby_locations': [
                        {'city': city, 'state': state, 'zipcode': zipcode}
                        for city, state, zipcode in nearby
                    ]
                })
            finally:
                session.close()
        
        return jsonify({'error': 'Location not found'}), 404
    except Exception as e:
        app.logger.error(f"IP location error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/map')
def map_view():
    """Render the map view page."""
    return render_template('map.html', map_html="")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
