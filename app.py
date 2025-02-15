from flask import Flask, render_template
from models import Session, PedicureListing
from sqlalchemy import text
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

@app.route('/')
def home():
    session = Session()
    try:
        # Query distinct states and their cities
        locations = session.query(
            PedicureListing.state,
            PedicureListing.city
        ).distinct().order_by(
            PedicureListing.state,
            PedicureListing.city
        ).all()

        # Organize into state-city dictionary
        states_cities = {}
        for state, city in locations:
            if state and city:  # Only include non-null values
                if state not in states_cities:
                    states_cities[state] = []
                if city not in states_cities[state]:  # Avoid duplicates
                    states_cities[state].append(city)

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
