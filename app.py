from flask import Flask, render_template, request, abort, jsonify, Response, url_for, redirect
from models import Session, PedicureListing
from sqlalchemy import text, func
import os
from dotenv import load_dotenv
import json
import re
from typing import Dict, Optional, List
import requests

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

@app.route('/sitemaps/state-<state_code>.xml')
def state_sitemap(state_code):
    """Generate sitemap for a specific state with links to city sitemaps"""
    session = Session()
    try:
        base_url = request.url_root.rstrip('/')
        state_code = state_code.upper()
        
        # Verify state exists and has listings
        has_listings = session.query(PedicureListing).filter(
            PedicureListing.state == state_code
        ).first() is not None
        
        if not has_listings:
            abort(404)
        
        # Get the state page URL
        state_url = f"{base_url}/pedicures-in/{state_code.lower()}"
        
        xml = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml.append('<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
        
        # Add the state page itself
        xml.append(f'''  <sitemap>
    <loc>{base_url}/sitemaps/state-page-{state_code.lower()}.xml</loc>
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
        
        # Add city sitemaps
        for city, last_updated in cities:
            if city:
                city_slug = city.lower().replace(' ', '-')
                lastmod = last_updated.strftime("%Y-%m-%d") if last_updated else datetime.now().strftime("%Y-%m-%d")
                xml.append(f'''  <sitemap>
    <loc>{base_url}/sitemaps/city-{state_code.lower()}-{city_slug}.xml</loc>
    <lastmod>{lastmod}</lastmod>
  </sitemap>''')
        
        xml.append('</sitemapindex>')
        return Response('\n'.join(xml), mimetype='application/xml')
    finally:
        session.close()

@app.route('/get_geoapify_location')
def get_geoapify_location():
    try:
        user_ip = request.headers.get('x-forwarded-for') or request.headers.get('x-real-ip') 
        if user_ip and ',' in user_ip:
            user_ip = user_ip.split(',')[0].strip()
        app.logger.info(f"Client IP detected: {user_ip}")
            
        url = f"https://api.geoapify.com/v1/ipinfo?ip={user_ip}&apiKey={GEOAPIFY_API_KEY}"
        headers = {
            "Accept": "application/json"
        }
        response = requests.get(url, headers=headers)
        
        
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

@app.route('/get_state_for_zipcode', methods=['GET'])
def get_state_for_zipcode():
    """Get state for a zipcode"""
    try:
        zipcode = request.args.get('zipcode')
        if not zipcode:
            return jsonify({'error': 'Missing zipcode'}), 400
            
        session = Session()
        try:
            # Find state for this zipcode
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

@app.route('/map/<location>')
def map_view_legacy(location):
    """Redirect old map URLs to new structure"""
    session = Session()
    try:
        # Check if location is a zipcode (5 digits) or city name
        if location.isdigit() and len(location) == 5:
            # Get state from zipcode
            listing = session.query(PedicureListing).filter(
                PedicureListing.zip_code == location
            ).first()
        else:
            # Convert URL format (e.g., "new-york") to proper city name ("New York")
            city_name = " ".join(word.capitalize() for word in location.split('-'))
            listing = session.query(PedicureListing).filter(
                func.lower(PedicureListing.city) == func.lower(city_name)
            ).first()
            
        if not listing:
            abort(404)
            
        # Redirect to new URL structure
        return redirect(url_for('map_view', state=listing.state.lower(), location=location))
    finally:
        session.close()

@app.route('/map/<state>/<location>')
def map_view(state, location):
    """Display a map of pedicure listings for a given location (zipcode or city) in a state"""
    session = Session()
    try:
        # Get filter parameters
        min_rating = request.args.get('rating', type=float)
        min_reviews = request.args.get('reviews', type=int)
        sort_by = request.args.get('sort', 'rating')  # Default sort by rating
        
        # Build base query
        query = session.query(PedicureListing).filter(
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
            "name": f"{len(listings)} Pedicure Places in {location_display}",
            "description": f"View {len(listings)} pedicure salons and nail spas in {location_display} on an interactive map. Compare ratings, services, and locations to find the best pedicure near you.",
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
        
        # Prepare schema data
        schema_data = {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": f"Cities with Pedicures in {state_name}",
            "description": f"Find pedicure services across {len(cities)} cities in {state_name}. Browse pedicures by city with ratings, hours, and contact information.",
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

        return render_template('state_listings.html',
                             state_code=state.upper(),
                             state_name=state_name,
                             cities=city_data,
                             schema_data=schema_data)
    finally:
        session.close()

@app.route('/pedicures-in/<state>/<city>')
def city_listings(state, city):
    """Display pedicure listings for a specific city in a state"""
    session = Session()
    try:
        # Convert state to uppercase for consistency
        state = state.upper()
        
        # First try exact match with the URL-formatted city name
        url_formatted_city = city.replace('-', ' ')
        
        # Query listings for the city and state
        listings = session.query(PedicureListing).filter(
            func.lower(func.regexp_replace(PedicureListing.city, '[^a-zA-Z0-9]+', ' ', 'g')) == 
            func.lower(url_formatted_city),
            func.upper(PedicureListing.state) == state,
            PedicureListing.coordinates.isnot(None)  # Ensure we have coordinates
        ).order_by(
            PedicureListing.rating.desc()
        ).all()
        
        if not listings:
            abort(404)
        
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

        return render_template('city_listings.html',
                             city=city_name,
                             state=state,
                             listings=listings,
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
def sitemap_index():
    """Generate sitemap index file"""
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
        
        # Add states sitemap
        xml.append(f'''  <sitemap>
    <loc>{base_url}/sitemaps/states.xml</loc>
    <lastmod>{datetime.now().strftime("%Y-%m-%d")}</lastmod>
  </sitemap>''')
        
        xml.append('</sitemapindex>')
        return Response('\n'.join(xml), mimetype='application/xml')
    finally:
        session.close()

@app.route('/sitemaps/static.xml')
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

@app.route('/sitemaps/states.xml')
def states_sitemap():
    """Generate sitemap for state pages with links to city sitemaps"""
    session = Session()
    try:
        base_url = request.url_root.rstrip('/')
        
        xml = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml.append('<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
        
        # Add state pages and link to their city sitemaps
        for state_code in STATE_NAMES.keys():
            # Check if state has any listings
            has_listings = session.query(PedicureListing).filter(
                PedicureListing.state == state_code
            ).first() is not None
            
            if has_listings:
                xml.append(f'''  <sitemap>
    <loc>{base_url}/sitemaps/state-{state_code.lower()}.xml</loc>
    <lastmod>{datetime.now().strftime("%Y-%m-%d")}</lastmod>
  </sitemap>''')
        
        xml.append('</sitemapindex>')
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

def parse_categories(categories: Optional[List[str]]) -> List[str]:
    """Convert categories list into list of strings"""
    if not categories:
        return []
    
    try:
        # Ensure each category is converted to string
        return [str(cat) for cat in categories]
    except (TypeError, ValueError):
        return []

from datetime import datetime

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

@app.route('/pedicures-in/<state>/<city>/<path:listing_path>')
def listing_page(state, city, listing_path):
    """Display a single pedicure listing"""
    session = Session()
    try:
        # Parse the listing path to get name and zipcode
        if '-' not in listing_path:
            abort(404)
            
        name_part = listing_path.rsplit('-', 1)[0]
        zipcode = listing_path.rsplit('-', 1)[1]
        
        # First try to find the listing by exact URL slug match
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
                func.lower(func.regexp_replace(PedicureListing.name, '[^a-zA-Z0-9\s]+', ' ', 'g')) == 
                name_part.replace('-', ' ')
            ).first()
        if not listing:
            abort(404)
            
        # Get nearby listings in same zipcode, ordered by rating
        nearby_listings = session.query(PedicureListing).filter(
            PedicureListing.zip_code == listing.zip_code,
            PedicureListing.id != listing.id,  # Use listing.id instead of listing_id
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
        state_code_lower = listing.state.lower()  # For URL generation
        
        # Parse hours and check if currently open
        hours_data = parse_hours(listing.hours)
        current_status = check_if_open(hours_data)
        # Prepare schema data
        schema_data = {
            "@context": "https://schema.org",
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
            "telephone": listing.phone,
            "url": listing.website if listing.website else request.url,
            "aggregateRating": {
                "@type": "AggregateRating",
                "ratingValue": str(listing.rating),
                "reviewCount": str(listing.reviews),
            },
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
            } if listing.coordinates else None
        }

        return render_template('listing.html', 
                             listing=listing,
                             nearby_listings=nearby_listings,
                             cities_in_state=cities_in_state,
                             state_code_lower=state_code_lower,
                             hours_data=hours_data,
                             current_status=current_status,
                             parse_hours=parse_hours,
                             parse_categories=parse_categories,
                             schema_data=schema_data)
    finally:
        session.close()

@app.route('/sitemaps/state-page-<state_code>.xml')
def state_page_sitemap(state_code):
    """Generate sitemap for a specific state page"""
    base_url = request.url_root.rstrip('/')
    state_code = state_code.upper()
    
    # Verify state exists
    if state_code not in STATE_NAMES:
        abort(404)
    
    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    
    # Add the state page
    xml.append(f'''  <url>
    <loc>{base_url}/pedicures-in/{state_code.lower()}</loc>
    <lastmod>{datetime.now().strftime("%Y-%m-%d")}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.7</priority>
  </url>''')
    
    xml.append('</urlset>')
    return Response('\n'.join(xml), mimetype='application/xml')

@app.route('/sitemaps/city-<state_code>-<city_name>.xml')
def city_sitemap(state_code, city_name):
    """Generate sitemap for a specific city with links to individual listings"""
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
        xml.append('<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
        
        # Add the city page itself
        xml.append(f'''  <sitemap>
    <loc>{base_url}/sitemaps/city-page-{state_code.lower()}-{city_name}.xml</loc>
    <lastmod>{datetime.now().strftime("%Y-%m-%d")}</lastmod>
  </sitemap>''')
        
        # Add listings sitemap
        xml.append(f'''  <sitemap>
    <loc>{base_url}/sitemaps/listings-{state_code.lower()}-{city_name}.xml</loc>
    <lastmod>{datetime.now().strftime("%Y-%m-%d")}</lastmod>
  </sitemap>''')
        
        xml.append('</sitemapindex>')
        return Response('\n'.join(xml), mimetype='application/xml')
    finally:
        session.close()

@app.route('/sitemaps/city-page-<state_code>-<city_name>.xml')
def city_page_sitemap(state_code, city_name):
    """Generate sitemap for a specific city page"""
    base_url = request.url_root.rstrip('/')
    state_code = state_code.upper()
    
    # We'll use the URL-formatted city name directly in the URL
    
    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    
    # Add the city page
    xml.append(f'''  <url>
    <loc>{base_url}/pedicures-in/{state_code.lower()}/{city_name}</loc>
    <lastmod>{datetime.now().strftime("%Y-%m-%d")}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.6</priority>
  </url>''')
    
    xml.append('</urlset>')
    return Response('\n'.join(xml), mimetype='application/xml')

@app.route('/sitemaps/listings-<state_code>-<city_name>.xml')
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

def check_if_open(hours_data: Dict[str, str]) -> Dict[str, any]:
    """Check if business is currently open based on hours data"""
    now = datetime.now()
    current_day = now.strftime("%A")  # Returns "Monday", "Tuesday", etc.
    current_time = now.hour * 100 + now.minute  # Convert to HHMM format
    
    # Get today's hours string
    today_hours = hours_data.get(current_day, "Not specified")
    
    # Handle cases where hours aren't specified
    if not today_hours or today_hours in ["Not specified", "Not Found", "Error parsing hours"]:
        return {
            "is_open": False,
            "status": "Hours not available",
            "status_class": "unknown"
        }
    
    # Split multiple time ranges (if any)
    time_ranges = [r.strip() for r in today_hours.split(",")]
    
    for time_range in time_ranges:
        try:
            open_time_str, close_time_str = time_range.split("-")
            
            # Parse opening time
            open_match = open_time_str.strip().upper()
            if ':' in open_match:
                open_hour = int(open_match.split(":")[0])
                open_minute = int(open_match.split(":")[1].split()[0])
            else:
                open_hour = int(open_match.split()[0])
                open_minute = 0
            
            if "PM" in open_match and open_hour != 12:
                open_hour += 12
            elif "AM" in open_match and open_hour == 12:
                open_hour = 0
            open_time = open_hour * 100 + open_minute
            
            # Parse closing time
            close_match = close_time_str.strip().upper()
            if ':' in close_match:
                close_hour = int(close_match.split(":")[0])
                close_minute = int(close_match.split(":")[1].split()[0])
            else:
                close_hour = int(close_match.split()[0])
                close_minute = 0
                
            if "PM" in close_match and close_hour != 12:
                close_hour += 12
            elif "AM" in close_match and close_hour == 12:
                close_hour = 0
            close_time = close_hour * 100 + close_minute
            
            # Check if current time falls within range
            if current_time >= open_time and current_time <= close_time:
                closing_time = datetime.now().replace(
                    hour=close_hour,
                    minute=close_minute
                ).strftime("%-I:%M %p")
                return {
                    "is_open": True,
                    "status": f"Open Now · Closes {closing_time}",
                    "status_class": "open"
                }
        except (ValueError, IndexError):
            continue
    
    return {
        "is_open": False,
        "status": "Closed Now",
        "status_class": "closed"
    }

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

@app.context_processor                                                                                    
def utility_processor():                                                                                  
     return {                                                                                              
         'STATE_NAMES': STATE_NAMES,
         'city_to_url_slug': city_to_url_slug,
         'to_url_slug': to_url_slug                                                                     
     }                                                                                                     
                          

