-- Add updated_at column
ALTER TABLE pedicure_listings ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Set initial values for existing records
UPDATE pedicure_listings SET updated_at = CURRENT_TIMESTAMP;

-- Add trigger to automatically update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_pedicure_listings_updated_at
    BEFORE UPDATE ON pedicure_listings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
