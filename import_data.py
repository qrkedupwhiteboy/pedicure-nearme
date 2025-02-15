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
