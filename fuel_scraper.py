import os
import sys
import time
import json
import logging

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from google.cloud import storage
from selenium.webdriver.chrome.service import Service




#Set up
fuel_choice_options = ["unleaded93", "unleaded95", "diesel500", "diesel50", "lrp93"]
fuel_choice = fuel_choice_options[1]
year_wanted = "2025"
inland_or_coastal = ["inland","coast"]
location_choice = inland_or_coastal[0]
data = {}

GOOGLE_BUCKET_NAME = os.environ.get("GOOGLE_BUCKET_NAME")


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()
CHROMEDRIVER_PATH = "/usr/bin/chromedriver"
CHROMIUM_BINARY_PATH = "/usr/bin/chromium"



chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--no-sandbox")
chrome_options.binary_location = CHROMIUM_BINARY_PATH
print("Chrome set up")
logging.info(f"Checking for chromedriver at: {chrome_options.arguments}")


logging.info(f"Checking for chromedriver at: {CHROMEDRIVER_PATH}")
if not os.path.exists(CHROMEDRIVER_PATH):
    logging.error(f"Chromedriver executable not found at {CHROMEDRIVER_PATH}!")
    logging.error("Please ensure 'chromium-driver' package is installed correctly in the Dockerfile.")
    sys.exit(1)

logging.info(f"Using Service with executable_path: {CHROMEDRIVER_PATH}")

service = Service(executable_path=CHROMEDRIVER_PATH)
logging.info("Initializing Chrome WebDriver...")

driver = webdriver.Chrome(service=service,options=chrome_options)
wait = WebDriverWait(driver, 5)
driver.get("https://aa.co.za/fuel-pricing/")

def scrape_fuel(fuel_choice,year_wanted,location_choice):

        try:
            print("Selecting fuel dropdown...")
            select_drop_down_fuel = wait.until(EC.element_to_be_clickable((By.ID, "edit-fuel-type")))
            select_fuel = Select(select_drop_down_fuel)
            print("Selecting fuel type")
            wait.until(EC.presence_of_element_located((By.XPATH,f"//select[@id='edit-fuel-type']/option[contains(., {fuel_choice})]")))
            select_fuel.select_by_value(fuel_choice)
            time.sleep(1)
            print(f"Selected {fuel_choice}")
            chosen_fuel = select_fuel.first_selected_option
            print(chosen_fuel.text)
        except Exception as e:
            print(f"Error {e} occurred")

        try:
            print("Selecting year dropdown...")
            select_drop_down_date = driver.find_element(By.ID, "edit-year")
            select_date = Select(select_drop_down_date)
            print("Selected dropdown")
            print("Waiting for year presence")
            wait.until(EC.presence_of_element_located((By.XPATH,f"//select[@id='edit-year']/option[contains(., {year_wanted})]")))
            print("Year presence found")
            select_date.select_by_visible_text(year_wanted)
            print(f"Selected {year_wanted} successfully")
        except Exception as e:
            print(f"Error {e} occurred")





        #Inland button
        try:

            print("Clicking inland button")
            inland_label_xpath = f"//label[input[@id='edit-location-{location_choice}']]"
            label_element = wait.until(EC.presence_of_element_located((By.XPATH, inland_label_xpath)))
            driver.execute_script("arguments[0].click();", label_element)
            print(f"{location_choice} button clicked successfully")
        except Exception as e:
            print(f"Error {e} occurred")

        #Get fuel price
        try:
            print("Clicking get fuel button")
            price_element = wait.until(EC.presence_of_element_located((By.ID, "edit-submit")))
            driver.execute_script("arguments[0].click();", price_element)
            print("price button clicked successfully")
        except Exception as e:
            print(f"Error {e} occurred")

        try:
            time.sleep(4)
            print("Getting price info...")
            price_div = driver.find_element(By.ID,"sr2")
            price_data = price_div.text
            print("price fetched")
            print(price_data)
            return price_data
        except Exception as e:
            print(f"Error {e} occurred")

def filter_string(data):
    wanted_part = data[-5:]
    return wanted_part


def save_data():
    bucket_name = GOOGLE_BUCKET_NAME
    project_id = "even-hull-456007-m4"
    storage_client = storage.Client(project=project_id)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob("scraped-data.json")  # Name of the file to be saved

    # Set options
    blob.upload_from_string(
        data=json.dumps(data),
        content_type="application/json"
    )

    print(f"Successfully scraped data and stored in gs://{bucket_name}/scraped-data.json")


if __name__ == '__main__':
    try:
        print("Trying")
        try:
            for fuel in fuel_choice_options:
                for location in inland_or_coastal:
                    print(f"Storing {fuel}.{location}")
                    result_rough = scrape_fuel(fuel,year_wanted,location)
                    result = filter_string(result_rough)
                    if result:
                        data[f"{fuel}.{location}"] = result
                        print(f"Successfully stored {fuel}.{location}")

            print(data)
        except Exception as e:
            print(f"Error {e} occurred")
        finally:
            driver.quit()

        try:
           save_data()
        except Exception as e:
            print(f"Error {e} occurred")


    except Exception as e:
        print(f"Error {e} occurred")

