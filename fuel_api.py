import os

from dotenv import load_dotenv
from google.cloud import storage
import json
import logging


#Constants
#Set as constant variables when pushed as google cloud funtions so dont need .env file anymore
SYNC_SECRET_KEY = os.environ.get("SYNC_SECRET_KEY")
GOOGLE_BUCKET_NAME = os.environ.get("GOOGLE_BUCKET_NAME")
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
data = {}


def fetch_data():
    global data

    logging.info("Server starting")

    bucket_name = "feul-prices"
    project_id = "even-hull-456007-m4"
    storage_client = storage.Client(project=project_id)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob("scraped-data.json")
    downloaded_data = blob.download_as_string()

    return json.loads(downloaded_data)


def set_up():
    global data
    try:
        logging.info("Server starting")
        data = fetch_data()
        logging.info("Server started and data fetched")
        return data
    except Exception as e:
        logging.error(f"Error: {e}")





def create_handler(request):
    global data
    path = request.path
    method = request.method

    if path == "/" and method == "GET":
        return json.dumps({"Message": "Welcome to Fuel Prices API"}), 200, {"Content-Type": "application/json"}


    if path.startswith("/fuel") and method == "GET":
        fuel_type = path.split("/fuel/")[1]
        fuel_price = data.get(fuel_type)
        if fuel_price is not None:
            return json.dumps({fuel_type:fuel_price}),200,{"Content-Type": "application/json"}
        else:
            return json.dumps({"error":f"Fuel type {fuel_type} not found"}, 400)



set_up()



