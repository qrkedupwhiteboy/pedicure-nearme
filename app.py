from flask import Flask, render_template
from models import Session, PedicureListing
from sqlalchemy import text
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

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
        return render_template('data.html', listings=listings)
    finally:
        session.close()

if __name__ == '__main__':
    app.run(debug=True)
