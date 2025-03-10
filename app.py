from flask import Flask, render_template, request, abort, jsonify, Response, url_for, redirect, current_app
from models import Session, PedicureListing
from sqlalchemy import text, func
import os
from dotenv import load_dotenv
import json
import re
from typing import Dict, Optional, List, Union
import requests
import pytz
import ipaddress
import ipinfo
from functools import wraps
from datetime import datetime, timedelta

# Create Flask app instance
app = Flask(__name__)
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import folium
from folium import Popup
import json
from sqlalchemy import or_
import requests
from requests.structures import CaseInsensitiveDict
from functools import lru_cache
import time



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

WEBHOOK_URL = os.getenv('email_webhook',)
IPINFO_API_KEY = os.getenv('ipinfo_api_key')
REVERSE_GEOCODE_KEY = os.getenv('REVERSE_GEOCODE_KEY')
app = Flask(__name__)

# Cache for sitemap and other infrequently changing data
_cache = {}

def cached_response(cache_key, expires_in_seconds=3600):
    """
    Decorator to cache responses for a specified time period.
    
    Args:
        cache_key: String or function to generate a cache key
        expires_in_seconds: Cache expiration time in seconds (default: 1 hour)
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Generate the cache key if it's a function
            key = cache_key(*args, **kwargs) if callable(cache_key) else cache_key
            
            # Check if we have a valid cached response
            if key in _cache:
                cached_data, expiry_time = _cache[key]
                if time.time() < expiry_time:
                    app.logger.debug(f"Cache hit for {key}")
                    return cached_data
            
            # Generate the response if not cached or expired
            app.logger.debug(f"Cache miss for {key}, generating response")
            response = f(*args, **kwargs)
            
            # Cache the response with expiration time
            _cache[key] = (response, time.time() + expires_in_seconds)
            
            return response
        return decorated_function
    return decorator

@app.route('/')
def home():
    session = Session()
    try:
        # Query cities with their listing counts - only select needed columns
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

@app.route('/sitemaps/cities-<state_code>.xml')
@cached_response(lambda state_code: f'cities_sitemap_{state_code.upper()}', expires_in_seconds=86400)  # Cache for 24 hours
def cities_sitemap(state_code):
    """Generate sitemap containing all city pages URLs for a specific state"""
    session = Session()
    try:
        base_url = request.url_root.rstrip('/')
        state_code = state_code.upper()
        
        # Verify state exists and has listings - only select id column
        has_listings = session.query(PedicureListing.id).filter(
            PedicureListing.state == state_code
        ).first() is not None
        
        if not has_listings:
            abort(404)
        
        # Get all cities in this state that have listings
        cities = session.query(
            PedicureListing.city,
            func.max(PedicureListing.updated_at).label('last_updated')
        ).filter(
            PedicureListing.state == state_code,
            PedicureListing.city.isnot(None)
        ).group_by(
            PedicureListing.city
        ).all()
        
        if not cities:
            abort(404)
            
        xml = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
        
        # Add all city pages directly
        for city, last_updated in cities:
            if city:
                city_slug = city.lower().replace(' ', '-')
                lastmod = last_updated.strftime("%Y-%m-%d") if last_updated else datetime.now().strftime("%Y-%m-%d")
                xml.append(f'''  <url>
    <loc>{base_url}/pedicures-in/{state_code.lower()}/{city_slug}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.6</priority>
  </url>''')
        
        xml.append('</urlset>')
        return Response('\n'.join(xml), mimetype='application/xml')
    finally:
        session.close()

def get_client_ip(request):
    """
    Retrieve client IP address from request headers.
    
    Returns:
    - IP address (IPv4 or IPv6)
    - None if no IP address found
    """
    # Retrieve potential IP addresses from headers
    user_ip = request.headers.get('x-forwarded-for') or request.headers.get('x-real-ip')
    if user_ip and ',' in user_ip:
        user_ip = user_ip.split(',')[0].strip()
    
    return user_ip

@app.route('/get_geoapify_location')
def get_geoapify_location():
    try:
        # Initialize the ipinfo handler
        handler = ipinfo.getHandler(IPINFO_API_KEY)
        
        # Get client IP
        user_ip = get_client_ip(request)
        app.logger.info(f"Client IP detected: {user_ip}")
        
        if not user_ip:
            app.logger.error("No IP address found in request headers")
            return jsonify({'error': 'Could not detect IP address'}), 400
        
        # Get location details from ipinfo
        details = handler.getDetails(user_ip)
        app.logger.info(f"ipinfo response: {details.all}")
        
        # Format response to match expected structure in frontend
        location_data = {
            'ip': details.ip,
            'location': {
                'latitude': float(details.loc.split(',')[0]) if details.loc else None,
                'longitude': float(details.loc.split(',')[1]) if details.loc else None,
                'city': details.city,
                'state': details.region,
                'country': details.country,
                'postal': details.postal
            }
        }
        
        app.logger.info(f"Formatted location data: {location_data}")
        return jsonify(location_data)
    except Exception as e:
        app.logger.error(f"Geoapify location error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_state_for_zipcode', methods=['GET'])
def get_state_for_zipcode():
    """Get state for a zipcode"""
    try:
        zipcode = request.args.get('zipcode')
        if not zipcode:
            return jsonify({'error': 'Missing zipcode'}), 400
            
        session = Session()
        try:
            # Find state for this zipcode - only select state column
            listing = session.query(PedicureListing.state).filter(
                PedicureListing.zip_code == zipcode
            ).first()
            
            if listing:
                return jsonify({'state': listing.state})
            else:
                return jsonify({'error': 'No state found for this zipcode'}), 404
        finally:
            session.close()
    except Exception as e:
        app.logger.error(f"State lookup error: {str(e)}")
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
                text("(coordinates::json->>'latitude')::float BETWEEN :lat_min AND :lat_max"),
                text("(coordinates::json->>'longitude')::float BETWEEN :lon_min AND :lon_max"),
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
                    'listing_count': loc.listing_count,
                    'url': url_for('map_view', state=loc.state.lower(), location=loc.zip_code if loc.zip_code else loc.city.lower().replace(' ', '-'), _external=True)
                }
                for loc in nearby
            ]
            
            return jsonify({'nearby_locations': locations})
            
        finally:
            session.close()
            
    except Exception as e:
        app.logger.error(f"Nearby locations error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/pedicures-in/<location>')
def legacy_city_redirect(location):
    """Redirect old URLs like /pedicures-in/wilton to new structure /pedicures-in/state/city"""
    # First check if this is a valid state code - if so, let the state_listings route handle it
    if location.upper() in STATE_NAMES:
        return state_listings(location)
        
    session = Session()
    try:
        # Convert URL format (e.g., "wilton") to proper city name for searching
        city_name = " ".join(word.capitalize() for word in location.split('-'))
        
        # Find the city in our database - only select needed columns
        listing = session.query(
            PedicureListing.city, 
            PedicureListing.state
        ).filter(
            func.lower(func.regexp_replace(PedicureListing.city, '[^a-zA-Z0-9]+', ' ', 'g')) == 
            func.lower(location.replace('-', ' '))
        ).first()
        
        if not listing:
            # If not found by exact match, try a more flexible approach
            listing = session.query(
                PedicureListing.city, 
                PedicureListing.state
            ).filter(
                func.lower(PedicureListing.city).like(f"%{location.replace('-', ' ')}%")
            ).first()
            
        if not listing:
            abort(404)
            
        # Redirect to new URL structure
        city_slug = city_to_url_slug(listing.city)
        return redirect(url_for('city_listings', 
                              state=listing.state.lower(), 
                              city=city_slug, 
                              _external=True))
    finally:
        session.close()

@app.route('/map/<location>')
def map_view_legacy(location):
    """Redirect old map URLs to new structure"""
    session = Session()
    try:
        # Check if location is a zipcode (5 digits) or city name
        if location.isdigit() and len(location) == 5:
            # Get state from zipcode - only select needed columns
            listing = session.query(
                PedicureListing.state,
                PedicureListing.city
            ).filter(
                PedicureListing.zip_code == location
            ).first()
        else:
            # Convert URL format (e.g., "new-york") to proper city name ("New York")
            city_name = " ".join(word.capitalize() for word in location.split('-'))
            listing = session.query(
                PedicureListing.state,
                PedicureListing.city
            ).filter(
                func.lower(PedicureListing.city) == func.lower(city_name)
            ).first()
            
        if not listing:
            abort(404)
            
        # Redirect to new URL structure
        return redirect(url_for('map_view', state=listing.state.lower(), location=location))
    finally:
        session.close()

@app.route('/map/<state>/<location>')
@cached_response(
    lambda state, location: (
        f'map_view_{state}_{location}_'
        f'rating_{request.args.get("rating", "")}_'
        f'reviews_{request.args.get("reviews", "")}_'
        f'sort_{request.args.get("sort", "rating")}'
    ), 
    expires_in_seconds=3600  # Cache for 1 hour
)
def map_view(state, location):
    """Display a map of pedicure listings for a given location (zipcode or city) in a state"""
    session = Session()
    try:
        # Get filter parameters
        min_rating = request.args.get('rating', type=float)
        min_reviews = request.args.get('reviews', type=int)
        sort_by = request.args.get('sort', 'rating')  # Default sort by rating
        
        # Build base query - select only needed columns
        query = session.query(
            PedicureListing.id,
            PedicureListing.name,
            PedicureListing.address,
            PedicureListing.city,
            PedicureListing.state,
            PedicureListing.zip_code,
            PedicureListing.phone,
            PedicureListing.website,
            PedicureListing.rating,
            PedicureListing.reviews,
            PedicureListing.coordinates
        ).filter(
            PedicureListing.coordinates.isnot(None),
            func.upper(PedicureListing.state) == state.upper()
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
        first_coords = json.loads(listings[0].coordinates)
        map_center = [first_coords['latitude'], first_coords['longitude']]
        m = folium.Map(location=map_center, zoom_start=13)
        
        # Add markers for each listing
        for listing in listings:
            coords = json.loads(listing.coordinates)
            listing_url = url_for('listing_page', state=listing.state.lower(), city=city_to_url_slug(listing.city), listing_path=to_url_slug(listing.name) + '-' + listing.zip_code, _external=True)
            popup_html = f"""
                <div class='listing-popup'>
                    <h3>{listing.name}</h3>
                    <p>{listing.address}</p>
                    <p class='rating'>Rating: {listing.rating}/5 ({listing.reviews} reviews)</p>
                    <p>{listing.phone}</p>
                    <a href='{listing_url}' target='_blank'>View Details</a>
                    {f"<a href='{listing.website}' target='_blank'>Visit Website</a>" if listing.website else ""}
                </div>
            """
            
            folium.Marker(
                location=[coords['latitude'], coords['longitude']],
                popup=Popup(popup_html, max_width=300),
                icon=folium.Icon(color='blue', icon='info-sign')
            ).add_to(m)
            
        # Format location name for display
        location_display = location
        if location.isdigit() and len(location) == 5:
            # If location is zipcode, get city name from first listing
            location_display = f"{listings[0].city}, {listings[0].state} {location}"
        else:
            # If location is city name, format it properly
            location_display = " ".join(word.capitalize() for word in location.split('-'))
            if listings:
                location_display = f"{location_display}, {listings[0].state}"

        # Prepare schema data
        schema_data = {
            "@context": "https://schema.org",
            "@type": "SearchResultsPage",
            "name": f"{len(listings)} Nail Salons and Pedicures in {location_display} - Map View",
            "description": f"View {len(listings)} nail salons and pedicures in {location_display} on an interactive map. Compare ratings, services, and locations to find the best salon open near you.",
            "about": {
                "@type": "Service",
                "serviceType": "Pedicure"
            },
            "mainEntity": {
                "@type": "ItemList",
                "numberOfItems": len(listings),
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": i + 1,
                        "item": {
                            "@type": "NailSalon",
                            "name": listing.name,
                            "address": {
                                "@type": "PostalAddress",
                                "streetAddress": listing.address,
                                "addressLocality": listing.city,
                                "addressRegion": listing.state,
                                "postalCode": listing.zip_code,
                                "addressCountry": "US"
                            },
                            "geo": {
                                "@type": "GeoCoordinates",
                                "latitude": json.loads(listing.coordinates)['latitude'] if listing.coordinates else None,
                                "longitude": json.loads(listing.coordinates)['longitude'] if listing.coordinates else None

                           } if listing.coordinates else None,
                            "telephone": listing.phone,
                            "url": listing.website if listing.website else None,
                            "aggregateRating": {
                                "@type": "AggregateRating",
                                "ratingValue": str(listing.rating),
                                "reviewCount": str(listing.reviews)
                            } if listing.rating and listing.reviews else None
                        }
                    } for i, listing in enumerate(listings)
                ]
            }
        }

        return render_template('map_view.html', 
                             map_html=m._repr_html_(), 
                             listings=listings,
                             location_display=location_display,
                             listing_count=len(listings),
                             state=state,
                             schema_data=schema_data)
    finally:
        session.close()

@app.route('/pedicures-in/<state>')
@cached_response(lambda state: f'state_listings_{state.upper()}_{request.args.get("page", 1)}', expires_in_seconds=3600)  # Cache for 1 hour
def state_listings(state):
    """Display pedicure listings for a specific state"""
    session = Session()
    try:
        # Get state name from code
        state_name = STATE_NAMES.get(state.upper())
        if not state_name:
            abort(404)
            
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = 50  # Number of cities per page
            
        # Query total count of cities for the state - only count distinct cities
        total_cities = session.query(
            func.count(func.distinct(PedicureListing.city))
        ).filter(
            func.upper(PedicureListing.state) == state.upper(),
            PedicureListing.city.isnot(None)
        ).scalar()
        
        # Query cities and their listing counts for the state with pagination
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
        ).offset((page - 1) * per_page).limit(per_page).all()
        
        if not cities and page == 1:
            abort(404)
            
        # Calculate pagination metadata
        total_pages = (total_cities + per_page - 1) // per_page
        has_prev = page > 1
        has_next = page < total_pages
        
        # Format city data
        city_data = [
            {'city': city[0], 'listing_count': city[1]}
            for city in cities
        ]
        
        # Prepare schema data
        schema_data = {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": f"Find Top Rated Nail Salons & Pedicures in {state_name} Open Today",
            "description": f"Find the best pedicures in {state_name}. Discover top-rated nail salons by city with real customer ratings, current hours, and easy booking for all pedicure types.",
            "about": {
                "@type": "Service",
                "serviceType": "Pedicure",
                "areaServed": {
                    "@type": "State",
                    "name": state_name,
                    "address": {
                        "@type": "PostalAddress",
                        "addressRegion": state.upper(),
                        "addressCountry": "US"
                    }
                }
            },
            "mainEntity": {
                "@type": "ItemList",
                "numberOfItems": len(cities),
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": i + 1,
                        "item": {
                            "@type": "City",
                            "name": city['city'],
                            "containedInPlace": {
                                "@type": "State",
                                "name": state_name
                            }
                        }
                    } for i, city in enumerate(city_data)
                ]
            }
        }

        # Pagination metadata for template
        pagination = {
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'total_items': total_cities,
            'has_prev': has_prev,
            'has_next': has_next,
            'prev_page': page - 1 if has_prev else None,
            'next_page': page + 1 if has_next else None
        }
        
        return render_template('state_listings.html',
                             state_code=state.upper(),
                             state_name=state_name,
                             cities=city_data,
                             pagination=pagination,
                             schema_data=schema_data)
    finally:
        session.close()

@app.route('/pedicures-in/<state>/<city>')
@cached_response(lambda state, city: f'city_listings_{state.upper()}_{city}_{request.args.get("page", 1)}', expires_in_seconds=3600)  # Cache for 1 hour
def city_listings(state, city):
    """Display pedicure listings for a specific city in a state"""
    session = Session()
    try:
        # Convert state to uppercase for consistency
        state = state.upper()
        
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = 20  # Number of listings per page
        
        # First try exact match with the URL-formatted city name
        url_formatted_city = city.replace('-', ' ')
        
        # Get total count of listings for pagination
        total_listings = session.query(func.count(PedicureListing.id)).filter(
            func.lower(func.regexp_replace(PedicureListing.city, '[^a-zA-Z0-9]+', ' ', 'g')) == 
            func.lower(url_formatted_city),
            func.upper(PedicureListing.state) == state,
            PedicureListing.coordinates.isnot(None)
        ).scalar()
        
        # Query listings for the city and state with pagination
        listings = session.query(PedicureListing).filter(
            func.lower(func.regexp_replace(PedicureListing.city, '[^a-zA-Z0-9]+', ' ', 'g')) == 
            func.lower(url_formatted_city),
            func.upper(PedicureListing.state) == state,
            PedicureListing.coordinates.isnot(None)  # Ensure we have coordinates
        ).order_by(
            PedicureListing.rating.desc()
        ).offset((page - 1) * per_page).limit(per_page).all()
        
        if not listings and page == 1:
            abort(404)
            
        # Calculate pagination metadata
        total_pages = (total_listings + per_page - 1) // per_page
        has_prev = page > 1
        has_next = page < total_pages
        
        # Get the actual city name from the first listing for display
        city_name = listings[0].city if listings else city.replace('-', ' ').title()
        
        # Prepare schema data
        schema_data = {
            "@context": "https://schema.org",
            "@type": "SearchResultsPage",
            "name": f"Pedicure Places in {city_name}, {state}",
            "description": f"Find top-rated pedicures in {city_name}, {state}. Browse and compare {len(listings)} manicure and pedicure services.",
            "about": {
                "@type": "Service",
                "serviceType": "Pedicure",
                "areaServed": {
                    "@type": "City",
                    "name": city_name,
                    "containedInPlace": {
                        "@type": "State",
                        "name": STATE_NAMES[state]
                    }
                }
            },
            "mainEntity": {
                "@type": "ItemList",
                "numberOfItems": len(listings),
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": i + 1,
                        "item": {
                            "@type": "NailSalon",
                            "name": listing.name,
                            "address": {
                                "@type": "PostalAddress",
                                "streetAddress": listing.address,
                                "addressLocality": listing.city,
                                "addressRegion": listing.state,
                                "postalCode": listing.zip_code,
                                "addressCountry": "US"
                            },
                            "geo": {
                                "@type": "GeoCoordinates",
                                "latitude": json.loads(listing.coordinates)['latitude'] if listing.coordinates else None,
                                "longitude": json.loads(listing.coordinates)['longitude'] if listing.coordinates else None
                            } if listing.coordinates else None,
                            "aggregateRating": {
                                "@type": "AggregateRating",
                                "ratingValue": str(listing.rating),
                                "reviewCount": str(listing.reviews)
                            } if listing.rating and listing.reviews else None
                        }
                    } for i, listing in enumerate(listings)
                ]
            }
        }

        # Pagination metadata for template
        pagination = {
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'total_items': total_listings,
            'has_prev': has_prev,
            'has_next': has_next,
            'prev_page': page - 1 if has_prev else None,
            'next_page': page + 1 if has_next else None
        }
        
        return render_template('city_listings.html',
                             city=city_name,
                             state=state,
                             listings=listings,
                             pagination=pagination,
                             schema_data=schema_data)
    finally:
        session.close()

@app.route('/about')
def about_page():
    schema_data = {
        "@context": "https://schema.org",
        "@type": "AboutPage",
        "name": "About Us - Find Your Perfect Pedicure",
        "description": "Learn about our community-driven platform dedicated to helping people find the perfect pedicure experience in their area. Discover quality nail care services near you.",
        "mainEntity": {
            "@type": "Organization",
            "name": "LocalPedicures",
            "description": "A platform helping people find and compare pedicure services across the United States.",
            "url": request.url_root,
            "areaServed": {
                "@type": "Country",
                "name": "United States"
            }
        }
    }
    return render_template('about.html', schema_data=schema_data)

@app.route('/contact')
def contact_page():
    schema_data = {
        "@context": "https://schema.org",
        "@type": "ContactPage",
        "name": "Contact Us - Find Your Perfect Pedicure",
        "description": "Get in touch with us about pedicure services, salon listings, or any questions about finding the perfect pedicure near you.",
        "mainEntity": {
            "@type": "Organization",
            "name": "LocalPedicures",
            "contactPoint": {
                "@type": "ContactPoint",
                "contactType": "customer service",
                "url": request.url
            }
        }
    }
    return render_template('contact.html', schema_data=schema_data)

@app.route('/sitemap.xml')
@cached_response('sitemap_index', expires_in_seconds=86400)  # Cache for 24 hours
def sitemap_index():
    """Generate sitemap index file that points to all other sitemaps"""
    session = Session()
    try:
        base_url = request.url_root.rstrip('/')
        
        # Build sitemap index XML
        xml = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml.append('<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
        
        # Add static pages sitemap
        xml.append(f'''  <sitemap>
    <loc>{base_url}/sitemaps/static.xml</loc>
    <lastmod>{datetime.now().strftime("%Y-%m-%d")}</lastmod>
  </sitemap>''')
        
        # Add state pages sitemap (contains all state pages)
        xml.append(f'''  <sitemap>
    <loc>{base_url}/sitemaps/state-pages.xml</loc>
    <lastmod>{datetime.now().strftime("%Y-%m-%d")}</lastmod>
  </sitemap>''')
        
        # Add all state-specific city sitemaps directly
        for state_code in STATE_NAMES.keys():
            # Check if state has any listings - only select id column
            has_listings = session.query(PedicureListing.id).filter(
                PedicureListing.state == state_code
            ).first() is not None
            
            if has_listings:
                xml.append(f'''  <sitemap>
    <loc>{base_url}/sitemaps/cities-{state_code.lower()}.xml</loc>
    <lastmod>{datetime.now().strftime("%Y-%m-%d")}</lastmod>
  </sitemap>''')
                
                # Get all cities in this state that have listings
                cities = session.query(
                    PedicureListing.city,
                    func.max(PedicureListing.updated_at).label('last_updated')
                ).filter(
                    PedicureListing.state == state_code,
                    PedicureListing.city.isnot(None)
                ).group_by(
                    PedicureListing.city
                ).all()
                
                # Add city listing sitemaps directly to the main index
                for city, last_updated in cities:
                    if city:
                        city_slug = city.lower().replace(' ', '-')
                        lastmod = last_updated.strftime("%Y-%m-%d") if last_updated else datetime.now().strftime("%Y-%m-%d")
                        xml.append(f'''  <sitemap>
    <loc>{base_url}/sitemaps/listings-{state_code.lower()}-{city_slug}.xml</loc>
    <lastmod>{lastmod}</lastmod>
  </sitemap>''')
        
        xml.append('</sitemapindex>')
        return Response('\n'.join(xml), mimetype='application/xml')
    finally:
        session.close()

@app.route('/sitemaps/static.xml')
@cached_response('static_sitemap', expires_in_seconds=604800)  # Cache for 1 week
def static_sitemap():
    """Generate sitemap for static pages"""
    base_url = request.url_root.rstrip('/')
    
    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    
    # Add static pages
    static_paths = ['', '/about', '/contact']
    for path in static_paths:
        xml.append(f'''  <url>
    <loc>{base_url}{path}</loc>
    <lastmod>{datetime.now().strftime("%Y-%m-%d")}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>''')
    
    xml.append('</urlset>')
    return Response('\n'.join(xml), mimetype='application/xml')

@app.route('/sitemaps/state-pages.xml')
@cached_response('state_pages_sitemap', expires_in_seconds=86400)  # Cache for 24 hours
def state_pages_sitemap():
    """Generate sitemap containing all state pages URLs"""
    session = Session()
    try:
        base_url = request.url_root.rstrip('/')
        
        xml = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
        
        # Add all state pages directly
        for state_code in STATE_NAMES.keys():
            # Check if state has any listings
            has_listings = session.query(PedicureListing).filter(
                PedicureListing.state == state_code
            ).first() is not None
            
            if has_listings:
                xml.append(f'''  <url>
    <loc>{base_url}/pedicures-in/{state_code.lower()}</loc>
    <lastmod>{datetime.now().strftime("%Y-%m-%d")}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.7</priority>
  </url>''')
        
        xml.append('</urlset>')
        return Response('\n'.join(xml), mimetype='application/xml')
    finally:
        session.close()

@app.route('/submit_contact', methods=['POST'])
def submit_contact():
    """Handle contact form submission"""
    try:
        data = request.get_json()
        
        # Get and validate form data
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        message = data.get('message', '').strip()
        
        # Basic validation
        if not name or len(name) < 2:
            return jsonify({'error': 'Please enter your name'}), 400
            
        if not email or '@' not in email:
            return jsonify({'error': 'Please enter a valid email address'}), 400
            
        if not message or len(message) < 10:
            return jsonify({'error': 'Please enter a message (minimum 10 characters)'}), 400
            
        # Get webhook URL from environment
        webhook_url = os.getenv('email_webhook')
        if not webhook_url:
            app.logger.error("Webhook URL not configured")
            return jsonify({'error': 'Contact form not properly configured'}), 500
            
        # Send to webhook
        response = requests.post(webhook_url, json=data)
        if not response.ok:
            app.logger.error(f"Webhook error: {response.status_code} - {response.text}")
            return jsonify({'error': 'Failed to send message'}), 500
            
        app.logger.info(f"Contact form submission from {name} ({email}) sent to webhook successfully")
        
        return jsonify({
            'success': True, 
            'message': 'Thank you for your message. We will respond shortly.'
        })
    except Exception as e:
        app.logger.error(f"Contact form error: {str(e)}")
        return jsonify({'error': 'Failed to send message'}), 500

import ast
from typing import List, Optional, Union

def parse_categories(categories: Optional[Union[List[str], str]]) -> List[str]:
    """Convert categories into a list of strings."""
    if not categories:
        return []
    
    if isinstance(categories, str):
        try:
            # Attempt to parse the string as a Python literal
            parsed_categories = ast.literal_eval(categories)
            if isinstance(parsed_categories, list):
                categories = parsed_categories
            else:
                return [categories]  # If it's not a list, treat it as a single category
        except (ValueError, SyntaxError):
            return [categories]  # If parsing fails, treat it as a single category
    
    if not isinstance(categories, list):
        return []
    
    return [str(cat) for cat in categories if cat]



from datetime import datetime



def parse_hours(hours_json: str) -> List[Dict[str, Union[str, List[str]]]]:
    """Parse hours from JSON text into a dictionary of day -> hours string"""
    if not hours_json:
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
        hours_array = json.loads(hours_json)
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
    
# check_if_open function removed - now handled by JavaScript

@app.route('/listing/<path:listing_path>')
def legacy_listing_redirect(listing_path):
    """Redirect old listing URLs to new structure"""
    session = Session()
    try:
        # Parse the listing path to get name and zipcode
        if '-' not in listing_path:
            abort(404)
            
        name_part = listing_path.rsplit('-', 1)[0]
        zipcode = listing_path.rsplit('-', 1)[1]
        
        # Find the listing
        listing = None
        listings = session.query(PedicureListing).filter(
            PedicureListing.zip_code == zipcode
        ).all()
        
        for potential_listing in listings:
            if to_url_slug(potential_listing.name) == name_part:
                listing = potential_listing
                break
                
        if not listing:
            # Try with a more flexible approach
            listing = session.query(PedicureListing).filter(
                PedicureListing.zip_code == zipcode
            ).filter(
                func.lower(func.regexp_replace(PedicureListing.name, '[^a-zA-Z0-9[:space:]]+', ' ', 'g')) == 
                name_part.replace('-', ' ')
            ).first()
            
        if not listing:
            abort(404)
            
        # Redirect to new URL structure
        city_slug = city_to_url_slug(listing.city)
        return redirect(url_for('listing_page', 
                              state=listing.state.lower(), 
                              city=city_slug, 
                              listing_path=listing_path,
                              _external=True))
    finally:
        session.close()

@app.route('/pedicures-in/<state>/<city>/<path:listing_path>')
@cached_response(lambda state, city, listing_path: f'listing_page_{state}_{city}_{listing_path}', expires_in_seconds=3600)  # Cache for 1 hour
def listing_page(state, city, listing_path):
    """Display a single pedicure listing"""
    session = Session()
    try:
        # Parse the listing path to get name and zipcode
        if '-' not in listing_path:
            abort(404)
            
        name_part = listing_path.rsplit('-', 1)[0]
        zipcode = listing_path.rsplit('-', 1)[1]
        
        # First try to find the listing by exact URL slug match - select all columns since we need the full object
        listings = session.query(PedicureListing).filter(
            PedicureListing.zip_code == zipcode
        ).all()
        
        listing = None
        for potential_listing in listings:
            if to_url_slug(potential_listing.name) == name_part:
                listing = potential_listing
                break
                
        # If not found, try a more flexible approach
        if not listing:
            # Try with the model's get_url_slug method
            listing = session.query(PedicureListing).filter(
                PedicureListing.zip_code == zipcode
            ).filter(
                func.lower(func.regexp_replace(PedicureListing.name, '[^a-zA-Z0-9[:space:]]+', ' ', 'g')) == 
                name_part.replace('-', ' ')
            ).first()
        if not listing:
            abort(404)
            
        # Get pagination parameters for nearby listings
        page = request.args.get('page', 1, type=int)
        per_page = 5  # Number of nearby listings per page
        
        # Get total count of nearby listings - only count id column
        total_nearby = session.query(func.count(PedicureListing.id)).filter(
            PedicureListing.zip_code == listing.zip_code,
            PedicureListing.id != listing.id,
            PedicureListing.coordinates.isnot(None)
        ).scalar()
        
        # Get nearby listings in same zipcode, ordered by rating with pagination - select only needed columns
        nearby_listings = session.query(
            PedicureListing.id,
            PedicureListing.name,
            PedicureListing.address,
            PedicureListing.city,
            PedicureListing.state,
            PedicureListing.zip_code,
            PedicureListing.phone,
            PedicureListing.website,
            PedicureListing.rating,
            PedicureListing.reviews,
            PedicureListing.coordinates
        ).filter(
            PedicureListing.zip_code == listing.zip_code,
            PedicureListing.id != listing.id,
            PedicureListing.coordinates.isnot(None)
        ).order_by(
            PedicureListing.rating.desc()
        ).offset((page - 1) * per_page).limit(per_page).all()
        
        # Calculate pagination metadata
        total_pages = (total_nearby + per_page - 1) // per_page
        has_prev = page > 1
        has_next = page < total_pages
        
        # Get cities in the same state that have listings - only select city column
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
        state_code_lower = listing.state.lower()  # For URL generation
        
        # Parse hours
        hours_data = parse_hours(listing.hours)
        # Prepare schema data
        parsed_categories = parse_categories(listing.categories)
        
        # Base URL for breadcrumbs
        base_url = request.url_root.rstrip('/')
        
        # Create schema data with multiple types
        parsed_categories_string = ", ".join(parsed_categories)
        schema_data = {
            "@context": "https://schema.org",
            "@graph": [
                # 1. LocalBusiness/NailSalon
                {
                    "@type": ["LocalBusiness", "NailSalon"],
                    "@id": request.url + "#business",
                    "name": listing.name,
                    "address": {
                        "@type": "PostalAddress",
                        "streetAddress": listing.address,
                        "addressLocality": listing.city,
                        "addressRegion": listing.state,
                        "postalCode": listing.zip_code,
                        "addressCountry": "US"
                    },
                    "telephone": listing.phone,
                    "url": listing.website if listing.website else request.url,
                    "aggregateRating": {
                        "@type": "AggregateRating",
                        "ratingValue": str(listing.rating),
                        "reviewCount": str(listing.reviews),
                    } if listing.rating and listing.reviews else None,
                    "openingHours": [
                        f"{day} {hours}" for day, hours in hours_data.items() 
                        if hours not in ["Not specified", "Not Found", "Error parsing hours"]
                    ],
                    "image": listing.featured_image[0] if listing.featured_image else None,
                    "priceRange": "$$",
                    "geo": {
                        "@type": "GeoCoordinates",
                        "latitude": json.loads(listing.coordinates).get('latitude') if listing.coordinates else None,
                        "longitude": json.loads(listing.coordinates).get('longitude') if listing.coordinates else None
                    } if listing.coordinates else None,
                    "keywords": ", ".join(parsed_categories + [
                        "pedicure",
                        f"pedicure in {listing.city}",
                        f"nail salon in {listing.city}",
                        f"nail spa in {listing.city}",
                        f"beauty salon in {listing.city}",
                        f"nail care in {listing.state}",
                        listing.name
                    ]),
                    "mainEntityOfPage": {
                        "@type": "WebPage",
                        "@id": request.url
                    },
                    "sameAs": listing.website if listing.website else None
                },
                
                # 2. Organization
                {
                    "@type": "Organization",
                    "@id": request.url + "#organization",
                    "name": listing.name,
                    "address": {
                        "@type": "PostalAddress",
                        "streetAddress": listing.address,
                        "addressLocality": listing.city,
                        "addressRegion": listing.state,
                        "postalCode": listing.zip_code,
                        "addressCountry": "US"
                    },
                    "contactPoint": {
                        "@type": "ContactPoint",
                        "telephone": listing.phone,
                        "contactType": "customer service"
                    } if listing.phone else None,
                    "url": listing.website if listing.website else request.url
                },
                
                # 3. BreadcrumbList
                {
                    "@type": "BreadcrumbList",
                    "@id": request.url + "#breadcrumb",
                    "itemListElement": [
                        {
                            "@type": "ListItem",
                            "position": 1,
                            "name": "Home",
                            "item": base_url
                        },
                        {
                            "@type": "ListItem",
                            "position": 2,
                            "name": STATE_NAMES.get(listing.state, listing.state),
                            "item": f"{base_url}/pedicures-in/{listing.state.lower()}"
                        },
                        {
                            "@type": "ListItem",
                            "position": 3,
                            "name": listing.city,
                            "item": f"{base_url}/pedicures-in/{listing.state.lower()}/{city_to_url_slug(listing.city)}"
                        },
                        {
                            "@type": "ListItem",
                            "position": 4,
                            "name": listing.name,
                            "item": request.url
                        }
                    ]
                },
                
                # 4. WebPage
                {
                    "@type": "WebPage",
                    "@id": request.url,
                    "url": request.url,
                    "name": f"Ratings and Info for {listing.name} in {listing.city} | LocalPedicures",
                    "description": f"{listing.name} offers top-rated {parsed_categories_string} services in {listing.city}, {listing.state}. View ratings, check if open today, and contact in just a few clicks.",
                    "breadcrumb": {"@id": request.url + "#breadcrumb"},
                    "primaryImageOfPage": {
                        "@type": "ImageObject",
                        "url": listing.featured_image[0] if listing.featured_image else None
                    } if listing.featured_image else None,
                    "mainEntity": {"@id": request.url + "#business"},
                    "isPartOf": {"@id": request.url + "#website"}
                },
                
                # 5. WebSite
                {
                    "@type": "WebSite",
                    "@id": request.url + "#website",
                    "url": base_url,
                    "name": "LocalPedicures",
                    "description": "Find top rated nail salons and pedicures near you",
                    "potentialAction": {
                        "@type": "SearchAction",
                        "target": {
                            "@type": "EntryPoint",
                            "urlTemplate": f"{base_url}/?q={{search_term_string}}"
                        },
                        "query-input": "required name=search_term_string"
                    }
                }
            ]
        }

        # Pagination metadata for template
        pagination = {
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'total_items': total_nearby,
            'has_prev': has_prev,
            'has_next': has_next,
            'prev_page': page - 1 if has_prev else None,
            'next_page': page + 1 if has_next else None
        }
        
        return render_template('listing.html', 
                             listing=listing,
                             nearby_listings=nearby_listings,
                             cities_in_state=cities_in_state,
                             state_code_lower=state_code_lower,
                             hours_data=hours_data,
                             parse_hours=parse_hours,
                             parse_categories=parse_categories,
                             pagination=pagination,
                             schema_data=schema_data)
    finally:
        session.close()

# This route is removed as it's now handled by state-pages.xml

# This route is removed as it's now handled by the main sitemap.xml

# This route is removed as it's now handled by cities-<state_code>.xml

@app.route('/sitemaps/listings-<state_code>-<city_name>.xml')
@cached_response(lambda state_code, city_name: f'listings_sitemap_{state_code.upper()}_{city_name}', expires_in_seconds=86400)  # Cache for 24 hours
def listings_sitemap(state_code, city_name):
    """Generate sitemap for individual listings in a specific city"""
    session = Session()
    try:
        base_url = request.url_root.rstrip('/')
        state_code = state_code.upper()
        
        # Convert URL-safe city name for querying
        url_formatted_city = city_name.replace('-', ' ')
        
        # Get all listings for this city
        listings = session.query(PedicureListing).filter(
            PedicureListing.state == state_code,
            func.lower(func.regexp_replace(PedicureListing.city, '[^a-zA-Z0-9]+', ' ', 'g')) == 
            func.lower(url_formatted_city)
        ).all()
        
        if not listings:
            abort(404)
        
        xml = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
        
        for listing in listings:
            lastmod = listing.updated_at.strftime("%Y-%m-%d") if listing.updated_at else datetime.now().strftime("%Y-%m-%d")
            city_slug = city_to_url_slug(listing.city)
            listing_slug = to_url_slug(listing.name) + '-' + listing.zip_code
            xml.append(f'''  <url>
    <loc>{base_url}/pedicures-in/{listing.state.lower()}/{city_slug}/{listing_slug}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.5</priority>
  </url>''')
            
        xml.append('</urlset>')
        return Response('\n'.join(xml), mimetype='application/xml')
    finally:
        session.close()

@app.route('/search_locations', methods=['GET'])
@cached_response(lambda: f'search_locations_{request.args.get("q", "")}', expires_in_seconds=1800)  # Cache for 30 minutes
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
    """Get zipcode from latitude and longitude or directly from IP"""
    try:
        # Check if lat/lon are provided
        lat = request.args.get('lat')
        lon = request.args.get('lon')
        
        # If coordinates are provided, use reverse geocoding
        if lat and lon:
            app.logger.info(f"Received coordinates: lat={lat}, lon={lon}")
            
            # Call reverse geocoding API
            url = f"https://api.geoapify.com/v1/geocode/reverse?lat={lat}&lon={lon}&apiKey={REVERSE_GEOCODE_KEY}"
            headers = {"Accept": "application/json"}
            response = requests.get(url, headers=headers)
            
            app.logger.debug(f"Calling URL: {response.url}")
            
            if not response.ok:
                app.logger.error(f"Reverse geocoding failed: {response.status_code}")
                return jsonify({'error': 'Reverse geocoding failed'}), response.status_code
                
            data = response.json()
            
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
        
        # If no coordinates, try to get zipcode directly from IP
        else:
            # Initialize the ipinfo handler
            handler = ipinfo.getHandler(IPINFO_API_KEY)
            
            # Get client IP
            user_ip = get_client_ip(request)
            app.logger.info(f"Getting zipcode for IP: {user_ip}")
            
            if not user_ip:
                app.logger.error("No IP address found in request headers")
                return jsonify({'error': 'Could not detect IP address'}), 400
            
            # Get location details from ipinfo
            details = handler.getDetails(user_ip)
            
            if details and details.postal:
                app.logger.info(f"Found zipcode from IP: {details.postal}")
                return jsonify({'zipcode': details.postal})
            else:
                app.logger.warning("No postal code found in ipinfo response")
                return jsonify({'error': 'No zipcode found for this IP'}), 404
            
    except Exception as e:
        app.logger.error(f"Zipcode lookup error: {str(e)}")
        return jsonify({'error': str(e)}), 500

def to_url_slug(text):
    """Convert any text to a URL-safe slug"""
    if not text:
        return ""
    # Replace non-alphanumeric characters with spaces
    text_clean = ''.join(c if c.isalnum() or c.isspace() else ' ' for c in text.lower())
    # Replace multiple spaces with single space
    while '  ' in text_clean:
        text_clean = text_clean.replace('  ', ' ')
    # Replace spaces with hyphens
    return text_clean.strip().replace(' ', '-')

def city_to_url_slug(city_name):
    """Convert a city name to a URL-safe slug"""
    return to_url_slug(city_name)

def url_slug_to_city_query(slug):
    """Convert a URL slug to a format suitable for database queries"""
    if not slug:
        return ""
    # Replace hyphens with spaces for querying
    return slug.replace('-', ' ')

@app.route('/admin/clear-cache', methods=['POST'])
def clear_cache():
    """Admin route to clear the cache"""
    # In a production environment, this should be protected with authentication
    api_key = request.headers.get('X-API-Key')
    if not api_key or api_key != os.getenv('ADMIN_API_KEY'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Check if a specific pattern was provided
    pattern = request.json.get('pattern', None) if request.is_json else None
    
    if pattern:
        # Clear only cache entries matching the pattern
        keys_to_remove = [k for k in _cache.keys() if pattern in k]
        for key in keys_to_remove:
            del _cache[key]
        app.logger.info(f"Cleared {len(keys_to_remove)} cache entries matching pattern: {pattern}")
        return jsonify({
            'success': True, 
            'message': f'Cleared {len(keys_to_remove)} cache entries matching pattern: {pattern}'
        })
    else:
        # Clear the entire cache
        cache_size = len(_cache)
        _cache.clear()
        app.logger.info(f"Cleared entire cache ({cache_size} entries)")
        return jsonify({'success': True, 'message': f'Cleared entire cache ({cache_size} entries)'})

@app.route('/admin/cache-stats', methods=['GET'])
def cache_stats():
    """Admin route to view cache statistics"""
    # In a production environment, this should be protected with authentication
    api_key = request.headers.get('X-API-Key')
    if not api_key or api_key != os.getenv('ADMIN_API_KEY'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Get current time for expiration calculation
    current_time = time.time()
    
    # Calculate statistics
    total_entries = len(_cache)
    expired_entries = sum(1 for _, (_, expiry) in _cache.items() if expiry < current_time)
    valid_entries = total_entries - expired_entries
    
    # Group by cache type
    cache_types = {}
    for key, (_, expiry) in _cache.items():
        # Extract the cache type from the key (e.g., 'sitemap', 'listing_page', etc.)
        if '_' in key:
            cache_type = key.split('_')[0]
            if cache_type not in cache_types:
                cache_types[cache_type] = 0
            cache_types[cache_type] += 1
    
    return jsonify({
        'total_entries': total_entries,
        'valid_entries': valid_entries,
        'expired_entries': expired_entries,
        'cache_types': cache_types,
        'cache_keys': list(_cache.keys())
    })

@app.context_processor                                                                                    
def utility_processor():                                                                                  
     return {                                                                                              
         'STATE_NAMES': STATE_NAMES,
         'city_to_url_slug': city_to_url_slug,
         'to_url_slug': to_url_slug                                                                     
     }

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors and try to redirect legacy URLs"""
    path = request.path
    
    # Check if this might be a legacy URL we can redirect
    if path.startswith('/pedicures-in/') and '/' in path[14:]:
        # Already using new URL structure, just a 404
        return render_template('404.html'), 404
        
    # Try to extract location from various URL patterns
    location = None
    if path.startswith('/pedicures-in/'):
        location = path[14:]
        # Check if this is a valid state code - if so, don't try to redirect
        if location.upper() in STATE_NAMES:
            return render_template('404.html'), 404
    elif path.startswith('/map/'):
        location = path[5:]
    elif path.startswith('/listing/'):
        return redirect(url_for('legacy_listing_redirect', listing_path=path[9:]))
        
    if location:
        # Try to find this location in our database
        session = Session()
        try:
            # First check if it's a zipcode
            if location.isdigit() and len(location) == 5:
                listing = session.query(
                    PedicureListing.city,
                    PedicureListing.state
                ).filter(
                    PedicureListing.zip_code == location
                ).first()
                
                if listing:
                    city_slug = city_to_url_slug(listing.city)
                    return redirect(url_for('city_listings', 
                                          state=listing.state.lower(), 
                                          city=city_slug,
                                          _external=True))
            
            # Then check if it's a city name
            location_query = location.replace('-', ' ').lower()
            listing = session.query(
                PedicureListing.city,
                PedicureListing.state
            ).filter(
                func.lower(func.regexp_replace(PedicureListing.city, '[^a-zA-Z0-9]+', ' ', 'g')) == 
                location_query
            ).first()
            
            if listing:
                city_slug = city_to_url_slug(listing.city)
                return redirect(url_for('city_listings', 
                                      state=listing.state.lower(), 
                                      city=city_slug,
                                      _external=True))
                                      
        finally:
            session.close()
    
    # If we couldn't find a redirect, return 404
    return render_template('404.html'), 404

