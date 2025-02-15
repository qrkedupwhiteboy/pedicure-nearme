import pandas as pd
from models import Session, PedicureListing, init_db
import sys
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

def import_csv_to_db(csv_path, chunk_size=10000):
    """
    Import large CSV file to PostgreSQL database in chunks
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
                # Extract city and state from address if they're null
                if pd.isna(record.get('city')) or pd.isna(record.get('state')):
                    address = record.get('address', '')
                    if address and isinstance(address, str):
                        parts = address.split(',')
                        if len(parts) >= 2:
                            # Last part usually contains state and zip
                            state_zip = parts[-1].strip().split()
                            if len(state_zip) >= 2:
                                record['state'] = state_zip[0]
                            # Second to last part usually contains city
                            record['city'] = parts[-2].strip()
                
                # Convert NaN/None to None for consistency
                for key in record:
                    if pd.isna(record[key]):
                        record[key] = None
                    elif key == 'website' and record[key] == 'NaN':
                        record[key] = None
            
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
