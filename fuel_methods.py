import os
import logging
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

SUPABASE_URL: str = os.environ.get("SUPABASE_URL")
SUPABASE_KEY: str = os.environ.get("SUPABASE_KEY")

# Initialize the Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

def get_latest_fuel_price(fuel_type: str, location: str):
    """
    Fetch the latest monthly row and extract the specific price for 
    the given fuel_type and location from the wide-row schema.
    """
    logger.info(f"Fetching latest fuel price for type: {fuel_type}, location: {location}")
    if not supabase:
        logger.error("Supabase client not initialized")
        return None
        
    response = supabase.table("fuel_prices").select("*") \
        .order("summary_month", desc=True) \
        .limit(1) \
        .execute()
    
    if not response.data:
        logger.warning("No data found in fuel_prices table")
        return None
        
    row = response.data[0]
    logger.info(f"Retrieved row for month: {row.get('summary_month')}")
    
    # Construct column name, e.g., "unleaded93_inland"
    column_name = f"{fuel_type.lower()}_{location.lower()}".replace(" ", "_")
    
    if column_name in row:
        data = {
            "id": row["id"],
            "fuel_type": fuel_type,
            "location": location,
            "price": row[column_name],
            "price_date": row["summary_month"]
        }
        logger.info(f"Found price for {column_name}: {row[column_name]}")
        return data
        
    logger.warning(f"Column {column_name} not found in retrieved data")
    return None

def get_all_latest_fuel_prices():
    """
    Fetch the latest monthly row and convert it into a list of 
    individual fuel price objects.
    """
    logger.info("Fetching all latest fuel prices")
    if not supabase:
        logger.error("Supabase client not initialized")
        return []
        
    response = supabase.table("fuel_prices").select("*") \
        .order("summary_month", desc=True) \
        .limit(1) \
        .execute()
    
    if not response.data:
        logger.warning("No data found in fuel_prices table")
        return []
        
    row = response.data[0]
    logger.info(f"Retrieved row for month: {row.get('summary_month')}")
    results = []
    
    # Define all price columns present in the wide row schema
    price_columns = [
        "unleaded93_inland", "unleaded93_coast",
        "unleaded95_inland", "unleaded95_coast",
        "diesel500_inland", "diesel500_coast",
        "diesel50_inland", "diesel50_coast",
        "lrp93_inland", "lrp93_coast"
    ]
    
    for col in price_columns:
        if col in row and row[col] is not None:
            parts = col.split("_")
            results.append({
                "id": row["id"],
                "fuel_type": parts[0],
                "location": parts[1],
                "price": row[col],
                "price_date": row["summary_month"]
            })
            
    logger.info(f"Returning {len(results)} fuel price records")
    return results

def get_latest_news(fuel_type: str = None):
    """
    Fetch the latest news summaries. If fuel_type is provided, 
    returns only that summary. Otherwise returns both.
    """
    logger.info(f"Fetching latest news (fuel_type filter: {fuel_type})")
    if not supabase:
        logger.error("Supabase client not initialized")
        return None
        
    response = supabase.table("fuel_prices").select("summary_month, petrol_news, diesel_news") \
        .order("summary_month", desc=True) \
        .limit(1) \
        .execute()
    
    logger.info(f"Supabase response data: {response.data}")
    
    if not response.data:
        logger.warning("No news data found in fuel_prices table")
        return None
        
    row = response.data[0]
    
    if fuel_type:
        key = f"{fuel_type.lower()}_news"
        if key in row:
            logger.info(f"Returning news for {fuel_type}")
            return {
                "month": row["summary_month"],
                "fuel_type": fuel_type,
                "summary": row[key]
            }
        logger.warning(f"Key {key} not found in news row")
        return None
        
    logger.info("Returning news for both fuel types")
    return {
        "month": row["summary_month"],
        "petrol": row["petrol_news"],
        "diesel": row["diesel_news"]
    }
