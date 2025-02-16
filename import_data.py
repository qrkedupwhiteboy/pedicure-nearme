import csv
import json
import os
import sys
from models import Session, Business
from dotenv import load_dotenv

def clean_json_string(json_str):
    """Clean and parse JSON string"""
    if not json_str:
        return None
    if isinstance(json_str, dict):
        return json_str
    try:
        # Try direct JSON parsing
        return json.loads(json_str)
    except:
        try:
            # Try cleaning and parsing
            cleaned = json_str.replace("'", '"')
            return json.loads(cleaned)
        except:
            # If all parsing fails, return as string
            return str(json_str)

def import_csv(filename):
    session = Session()
    row_count = 0
    error_count = 0
    
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            
            for row_num, row in enumerate(csv_reader, 1):
                try:
                    business = Business(
                        name=row.get('name'),
                        description=row.get('description'),
                        reviews=float(row.get('reviews', 0)) if row.get('reviews') else 0,
                        rating=float(row.get('rating', 0)) if row.get('rating') else 0,
                        website=row.get('website'),
                        phone=row.get('phone'),
                        featured_image=row.get('featured_image'),
                        main_category=row.get('main_category'),
                        categories=clean_json_string(row.get('categories')),
                        address=row.get('address'),
                        review_keywords=clean_json_string(row.get('review_keywords')),
                        link=row.get('link'),
                        reviews_per_rating=clean_json_string(row.get('reviews_per_rating')),
                        coordinates=clean_json_string(row.get('coordinates')),
                        hours=clean_json_string(row.get('hours')),
                        detailed_reviews=clean_json_string(row.get('detailed_reviews'))
                    )
                    session.add(business)
                    row_count += 1
                    
                    # Commit in batches of 100 to avoid memory issues
                    if row_count % 100 == 0:
                        session.commit()
                        print(f"Processed {row_count} records...")
                
                except Exception as e:
                    error_count += 1
                    print(f"Error processing row {row_num}: {str(e)}")
                    continue
            
            # Final commit for remaining records
            session.commit()
            print(f"\nImport completed:")
            print(f"Successfully imported {row_count} records")
            print(f"Errors encountered: {error_count}")
            
    except Exception as e:
        print(f"Fatal error occurred: {str(e)}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    load_dotenv()
    
    if len(sys.argv) != 2:
        print("Usage: python import_data.py <csv_file_path>")
        sys.exit(1)
        
    csv_file = sys.argv[1]
    if not os.path.exists(csv_file):
        print(f"Error: File '{csv_file}' does not exist")
        sys.exit(1)
        
    print(f"Importing data from: {csv_file}")
    import_csv(csv_file)
