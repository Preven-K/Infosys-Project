import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import os
import time
import datetime
import zipfile
import shutil
import hashlib
import threading

# Helper Functions
def initialize_driver(download_dir):
    options = Options()
    prefs = {
        "download.default_directory": download_dir,
        "profile.default_content_settings.popups": 0,
        "download.prompt_for_download": False,
        "safebrowsing.enabled": True
    }
    options.add_experimental_option("prefs", prefs)

    # Configure for headless operation and cloud compatibility
    options.add_argument("--headless")  # Run in headless mode
    options.add_argument("--no-sandbox")  # Disable sandbox for Linux environments
    options.add_argument("--disable-dev-shm-usage")  # Prevent resource issues in containers

    # Path to the Chromium binary on Streamlit Cloud
    options.binary_location = "/usr/bin/chromium-browser"  # Update the location based on the container path
    
    # Automatically download and configure the correct chromedriver for the environment
    service = Service(ChromeDriverManager().install())  # This automatically installs the correct chromedriver

    driver = webdriver.Chrome(service=service, options=options)
    return driver

def organize_files_by_type(file_path, base_folder, log_file):
    if os.path.isfile(file_path):
        file_extension = os.path.splitext(file_path)[1].lower().lstrip(".")
        file_type_folder = os.path.join(base_folder, file_extension.upper())

        if not os.path.exists(file_type_folder):
            os.makedirs(file_type_folder)

        destination_path = os.path.join(file_type_folder, os.path.basename(file_path))

        if os.path.exists(destination_path):
            # Check for duplicates
            if not is_duplicate(file_path, destination_path):
                shutil.move(file_path, destination_path)
                log_message = f"✅ Added {os.path.basename(file_path)} to {file_type_folder}\n"
            else:
                os.remove(file_path)
                log_message = f"❌ Removed duplicate file: {os.path.basename(file_path)}\n"
        else:
            shutil.move(file_path, destination_path)
            log_message = f"✅ Added {os.path.basename(file_path)} to {file_type_folder}\n"

        log_file.write(log_message)
        st.write(log_message)


def is_duplicate(file1, file2):
    return hash_file(file1) == hash_file(file2)


def hash_file(file_path):
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

# Main Application
def download_reports(download_dir, current_date, log_file):
    # Initialize WebDriver
    driver = None  # Initialize driver to handle exceptions properly

    try:
        driver = initialize_driver(download_dir)
        driver.get("https://www.nseindia.com/all-reports")

        # Wait for the page to load
        wait = WebDriverWait(driver, 30)
        wait.until(EC.presence_of_element_located((By.XPATH, "//span[@class='checkmark']")))
        st.write("Records loaded successfully.")

        # Scroll to the bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(5)

        # Select checkboxes
        checkbox = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[@class='checkmark']")))
        driver.execute_script("arguments[0].click();", checkbox)
        st.write("All files selected successfully.")

        # Click download button
        download_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//i[contains(@class, 'fa fa-download')]")))
        driver.execute_script("arguments[0].click();", download_button)
        st.write("Download button clicked successfully.")
        time.sleep(10)

        # Process files
        downloaded_files = [f for f in os.listdir(download_dir) if f.endswith(".zip")]
        if downloaded_files:
            st.write(f"Downloaded ZIP files: {downloaded_files}")

            for file in downloaded_files:
                zip_file_path = os.path.join(download_dir, file)
                new_file_name = f"Downloads_{current_date}.zip"
                renamed_zip_path = os.path.join(download_dir, new_file_name)

                try:
                    os.rename(zip_file_path, renamed_zip_path)
                    log_message = f"✅ Renamed '{file}' to '{new_file_name}'\n"
                    log_file.write(log_message)
                    st.write(log_message)
                except Exception as e:
                    log_message = f"❌ Error renaming '{file}': {e}\n"
                    log_file.write(log_message)
                    st.write(log_message)

                # Extract and organize files
                extract_folder = os.path.join(download_dir, "Extracted")
                if not os.path.exists(extract_folder):
                    os.makedirs(extract_folder)

                with zipfile.ZipFile(renamed_zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_folder)
                    st.write(f"✅ Extracted {new_file_name} to {extract_folder}")

                for extracted_file in os.listdir(extract_folder):
                    extracted_file_path = os.path.join(extract_folder, extracted_file)
                    if os.path.isfile(extracted_file_path):
                        organize_files_by_type(extracted_file_path, download_dir, log_file)

                os.remove(renamed_zip_path)
                st.write(f"🗑️ Deleted original ZIP file: {renamed_zip_path}")

            st.write("File processing complete.")
        else:
            st.error("No ZIP files found in the download directory.")

    except Exception as e:
        st.error(f"An error occurred: {e}")
    finally:
        if driver:
            driver.quit()

# Main Application
def main():
    st.title("NSE Automation Tool")
    st.write("Automate file downloads, organization, and log generation for NSE reports.")

    # Date input for scheduling
    st.subheader("Schedule Automatic Download")
    download_date = st.date_input("Select Date for Automatic Download", min_value=datetime.date.today())

    # Start download on button click
    start_process = st.button("Start Automation")

    if start_process:
        # Prepare the environment for download
        download_dir = "/mnt/data"  # Make sure this is correct for your environment (update if needed)
        current_date = download_date.strftime("%d.%m.%Y")
        date_folder_path = os.path.join(download_dir, current_date)

        if not os.path.exists(date_folder_path):
            os.makedirs(date_folder_path)

        log_file_path = os.path.join(date_folder_path, f"{current_date}.log")
        with open(log_file_path, "w", encoding="utf-8") as log_file:
            # Start download process immediately
            download_reports(download_dir, current_date, log_file)
    
    # Automatically schedule downloads (for the selected date)
    schedule_button = st.button("Schedule Download for Selected Date")
    if schedule_button:
        st.write(f"Download scheduled for {download_date}.")
        # You can use threading or scheduling libraries to run the download process at the given time
        # For simplicity, we can simulate it with a delay
        delay = (download_date - datetime.date.today()).days * 86400  # Delay in seconds
        if delay > 0:
            threading.Timer(delay, download_reports, args=(download_dir, download_date.strftime("%d.%m.%Y"), open(log_file_path, "w", encoding="utf-8"))).start()

if __name__ == "__main__":
    main()
