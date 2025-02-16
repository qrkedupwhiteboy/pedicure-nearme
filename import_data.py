import pandas as pd
from models import Session, PedicureListing, init_db
import sys
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv
import json

def import_csv_to_db(csv_path, chunk_size=10000):
    """
    Import CSV file to PostgreSQL database in chunks
    """
    load_dotenv()
    
    print(f"Starting import of {csv_path}")
    
    # Initialize database tables
    init_db()
    
    # Create database engine
    engine = create_engine(os.getenv('DATABASE_URL'))
    
    # Read and process CSV in chunks
    chunks = pd.read_csv(csv_path, chunksize=chunk_size)
    total_rows = 0
    
    for chunk_number, chunk in enumerate(chunks, 1):
        # Convert chunk to dict for bulk insert
        records = chunk.to_dict('records')
        
        # Create session
        session = Session()
        
        try:
            # Process records before insert
            for record in records:
                # Handle JSON fields and convert NaN/None to None for consistency
                for key in record:
                    if pd.isna(record[key]):
                        record[key] = None
                    elif key == 'website' and record[key] == 'NaN':
                        record[key] = None
                    elif key in ['categories', 'review_keywords', 'reviews_per_rating', 
                               'coordinates', 'hours', 'detailed_reviews']:
                        try:
                            if isinstance(record[key], str):
                                # Validate and parse JSON format
                                parsed_json = json.loads(record[key])
                                record[key] = json.dumps(parsed_json)  # Normalize JSON formatting
                            else:
                                record[key] = None
                        except (json.JSONDecodeError, TypeError) as e:
                            print(f"Error parsing JSON for {key} in record: {str(e)}")
                            record[key] = None
                
                # Ensure description and detailed_reviews don't exceed 10000 characters
                if record.get('description'):
                    record['description'] = record['description'][:10000]
                if record.get('detailed_reviews'):
                    record['detailed_reviews'] = record['detailed_reviews'][:10000]
            
            # Bulk insert chunk
            session.bulk_insert_mappings(PedicureListing, records)
            session.commit()
            
            rows_imported = len(records)
            total_rows += rows_imported
            print(f"Chunk {chunk_number}: Imported {rows_imported} rows. Total: {total_rows}")
        except Exception as e:
            print(f"Error importing chunk {chunk_number}: {str(e)}")
            session.rollback()
        finally:
            session.close()
    
    print(f"Import completed. Total rows imported: {total_rows}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python import_data.py <path_to_csv_file>")
        sys.exit(1)
        
    csv_path = sys.argv[1]
    import_csv_to_db(csv_path)
