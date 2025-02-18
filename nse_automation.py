import os
import time
import datetime
import zipfile
import shutil
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import streamlit as st

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# Download directory
BASE_DOWNLOAD_DIR = "Downloads/NSE"
LOG_FILE = "process.log"

# Initialize WebDriver
def initialize_driver(retry_count=0):
    if retry_count > 3:
        raise Exception("Failed to initialize WebDriver after 3 retries.")
    try:
        logger.info("Initializing WebDriver...")
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        prefs = {"download.default_directory": os.path.abspath(BASE_DOWNLOAD_DIR),
                 "profile.default_content_settings.popups": 0,
                 "download.prompt_for_download": False,
                 "safebrowsing.enabled": True}
        chrome_options.add_experimental_option("prefs", prefs)
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        logger.error(f"Error initializing WebDriver: {e}. Retrying...")
        time.sleep(3)
        return initialize_driver(retry_count + 1)

# Organize files by type
def organize_files_by_type(file_path, base_folder):
    file_extension = os.path.splitext(file_path)[1].lower().lstrip(".")
    folder_name = file_extension.upper() if file_extension else "OTHER"
    target_folder = os.path.join(base_folder, folder_name)
    os.makedirs(target_folder, exist_ok=True)
    shutil.move(file_path, os.path.join(target_folder, os.path.basename(file_path)))
    logger.info(f"Moved file to {target_folder}")

# Extract nested ZIP files
def extract_nested_zip(zip_path, base_folder):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        nested_folder = os.path.join(base_folder, "NestedExtracted")
        os.makedirs(nested_folder, exist_ok=True)
        zip_ref.extractall(nested_folder)
        logger.info(f"Extracted nested ZIP {zip_path} into {nested_folder}")

        for root, _, files in os.walk(nested_folder):
            for file in files:
                extracted_path = os.path.join(root, file)
                if file.endswith(".zip"):
                    extract_nested_zip(extracted_path, base_folder)
                    os.remove(extracted_path)
                else:
                    organize_files_by_type(extracted_path, base_folder)
        shutil.rmtree(nested_folder)

# Process extracted folder
def process_extracted_folder(base_folder):
    extracted_folder = os.path.join(base_folder, "extracted")
    if os.path.exists(extracted_folder):
        logger.info(f"Processing folder: {extracted_folder}")
        for root, _, files in os.walk(extracted_folder):
            for file in files:
                file_path = os.path.join(root, file)
                if file.endswith(".zip"):
                    extract_nested_zip(file_path, base_folder)
                    os.remove(file_path)
                else:
                    organize_files_by_type(file_path, base_folder)
        shutil.rmtree(extracted_folder)

# Main function
def main():
    st.title("NSE File Downloader and Organizer")
    if st.button("Start Download Process"):
        current_date = datetime.datetime.now().strftime("%d.%m.%Y")
        date_folder = os.path.join(BASE_DOWNLOAD_DIR, current_date)
        os.makedirs(date_folder, exist_ok=True)

        driver = initialize_driver()
        try:
            driver.get("https://www.nseindia.com/all-reports")
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, "//span[@class='checkmark']"))
            )
            time.sleep(5)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, "//span[@class='checkmark']"))
            ).click()
            WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, "//i[contains(@class, 'fa fa-download')]"))
            ).click()
            time.sleep(15)

            zip_files = [f for f in os.listdir(BASE_DOWNLOAD_DIR) if f.endswith(".zip")]
            if not zip_files:
                logger.warning("No ZIP files found. Retrying...")
                main()
                return

            for zip_file in zip_files:
                zip_path = os.path.join(BASE_DOWNLOAD_DIR, zip_file)
                extract_folder = os.path.join(date_folder, "Extracted")
                os.makedirs(extract_folder, exist_ok=True)

                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_folder)
                    logger.info(f"Extracted {zip_file} into {extract_folder}")

                for extracted_file in os.listdir(extract_folder):
                    file_path = os.path.join(extract_folder, extracted_file)
                    if os.path.isfile(file_path):
                        if extracted_file.endswith(".zip"):
                            extract_nested_zip(file_path, date_folder)
                        else:
                            organize_files_by_type(file_path, date_folder)
                process_extracted_folder(date_folder)
                os.remove(zip_path)
        except Exception as e:
            logger.error(f"Error during download process: {e}")
        finally:
            driver.quit()

# Run the app
if __name__ == "__main__":
    main()
