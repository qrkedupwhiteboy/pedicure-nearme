from flask import Flask, render_template
from models import Session, PedicureListing
from sqlalchemy import text, func
import os
from dotenv import load_dotenv

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
            if state:  # Only include non-null values
                if state not in states_cities:
                    states_cities[state] = {'top_cities': [], 'total_cities': 0}
                if len(states_cities[state]['top_cities']) < 5:
                    states_cities[state]['top_cities'].append(city)
                states_cities[state]['total_cities'] += 1

        return render_template('index.html', states_cities=states_cities)
    finally:
        session.close()

@app.route('/search')
def search():
    session = Session()
    try:
        # Example query - we'll expand this later
        listings = session.query(PedicureListing).limit(50).all()
        return render_template('search.html', listings=listings)
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
