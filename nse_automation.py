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

##################################################################################################
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
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def organize_files_by_type(file_path, base_folder, log_file):
    if os.path.isfile(file_path):
        file_extension = os.path.splitext(file_path)[1].lower().lstrip(".")
        file_type_folder = os.path.join(base_folder, file_extension.upper())

        if not os.path.exists(file_type_folder):
            os.makedirs(file_type_folder)

        destination_path = os.path.join(file_type_folder, os.path.basename(file_path))
        shutil.move(file_path, destination_path)
        log_message = f"✅ Added {os.path.basename(file_path)} to {file_type_folder}\n"
        log_file.write(log_message)
        st.write(log_message)

##################################################################################################
# Main Application
def main():
    st.title("NSE Automation Tool")
    st.write("Automate file downloads, organization, and log generation for NSE reports.")

    # User Input Section
    st.subheader("Login Details")
    username = st.text_input("Enter Username:")
    password = st.text_input("Enter Password:", type="password")
    start_process = st.button("Start Automation")

    if start_process:
        if not username or not password:
            st.error("Please enter valid login details.")
        else:
            st.success("Login successful. Starting automation process...")

            # Set up directories
            download_dir = "C:\\Users\\kprev\\Downloads\\NSE"
            current_date = datetime.datetime.now().strftime("%d.%m.%Y")
            date_folder_path = os.path.join(download_dir, current_date)

            if not os.path.exists(date_folder_path):
                os.makedirs(date_folder_path)

            log_file_path = os.path.join(date_folder_path, f"{current_date}.log")
            with open(log_file_path, "w", encoding="utf-8") as log_file:
                try:
                    # Initialize WebDriver
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
                            extract_folder = os.path.join(date_folder_path, "Extracted")
                            if not os.path.exists(extract_folder):
                                os.makedirs(extract_folder)

                            with zipfile.ZipFile(renamed_zip_path, 'r') as zip_ref:
                                zip_ref.extractall(extract_folder)
                                st.write(f"✅ Extracted {new_file_name} to {extract_folder}")

                            for extracted_file in os.listdir(extract_folder):
                                extracted_file_path = os.path.join(extract_folder, extracted_file)
                                if os.path.isfile(extracted_file_path):
                                    organize_files_by_type(extracted_file_path, date_folder_path, log_file)

                            os.remove(renamed_zip_path)
                            st.write(f"🗑️ Deleted original ZIP file: {renamed_zip_path}")

                        st.write("File processing complete.")
                    else:
                        st.error("No ZIP files found in the download directory.")

                except Exception as e:
                    st.error(f"An error occurred: {e}")
                finally:
                    driver.quit()
