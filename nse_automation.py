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

# Global variables
download_dir = "C:\\Users\\kprev\\Downloads\\NSE"

# Streamlit UI
st.title("NSE Report Downloader and Organizer")
st.sidebar.header("Settings")
download_dir = st.sidebar.text_input("Download Directory", value=download_dir)
retry_limit = st.sidebar.number_input("Retry Limit", min_value=1, max_value=10, value=3, step=1)

st.sidebar.subheader("Run the Script")
if st.sidebar.button("Start Download Process"):
    with st.spinner("Initializing the download process..."):
        # Initialize Selenium WebDriver
        options = Options()
        prefs = {
            "download.default_directory": download_dir,
            "profile.default_content_settings.popups": 0,
            "download.prompt_for_download": False,
            "safebrowsing.enabled": True
        }
        options.add_experimental_option("prefs", prefs)

        def initialize_driver():
            return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        retry_count = 0
        def retry_download():
            nonlocal retry_count
            retry_count += 1
            if retry_count > retry_limit:
                st.error("Retry limit reached. Exiting.")
                return False
            st.warning(f"Retrying... Attempt {retry_count}/{retry_limit}")
            time.sleep(5)
            main()

        def organize_files_by_type(file_path, base_folder, log_file):
            if os.path.isfile(file_path):
                file_extension = os.path.splitext(file_path)[1].lower().lstrip(".")
                file_type_folder = os.path.join(base_folder, file_extension.upper())

                if not os.path.exists(file_type_folder):
                    os.makedirs(file_type_folder)

                destination_path = os.path.join(file_type_folder, os.path.basename(file_path))
                shutil.move(file_path, destination_path)
                log_file.write(f"✅ Added {os.path.basename(file_path)} to {file_type_folder}\n")
                st.success(f"Added {os.path.basename(file_path)} to {file_type_folder}")

        def remove_duplicate_files(folder_path, log_file):
            file_hashes = {}
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    file_hash = hashlib.md5(open(file_path, 'rb').read()).hexdigest()

                    if file_hash in file_hashes:
                        os.remove(file_path)
                        log_file.write(f"❌ Removed duplicate file: {file_path}\n")
                        st.warning(f"Removed duplicate file: {file_path}")
                    else:
                        file_hashes[file_hash] = file_path

        def main():
            driver = initialize_driver()
            try:
                driver.get("https://www.nseindia.com/all-reports")

                # Wait for the page to load
                wait = WebDriverWait(driver, 30)
                wait.until(EC.presence_of_element_located((By.XPATH, "//span[@class='checkmark']")))
                st.success("Records loaded successfully!")

                # Scroll to the bottom to ensure all elements are loaded
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(5)

                # Select the checkbox for all files
                checkbox = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//span[@class='checkmark']"))
                )
                driver.execute_script("arguments[0].click();", checkbox)
                st.success("All files selected successfully.")

                # Wait for and click the "Download" button
                download_button = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//i[contains(@class, 'fa fa-download')]"))
                )
                driver.execute_script("arguments[0].click();", download_button)
                st.success("Download button clicked successfully.")

                # Wait for file download to complete
                time.sleep(10)

                # Renaming and processing ZIP files
                downloaded_files = [f for f in os.listdir(download_dir) if f.endswith(".zip")]
                if downloaded_files:
                    current_date = datetime.datetime.now().strftime("%d.%m.%Y")
                    date_folder_path = os.path.join(download_dir, current_date)
                    os.makedirs(date_folder_path, exist_ok=True)

                    log_file_path = os.path.join(date_folder_path, f"{current_date}.log")
                    with open(log_file_path, "w", encoding="utf-8") as log_file:
                        for file in downloaded_files:
                            zip_file_path = os.path.join(download_dir, file)
                            renamed_zip_path = os.path.join(download_dir, f"Downloads_{current_date}.zip")
                            os.rename(zip_file_path, renamed_zip_path)

                            extract_folder = os.path.join(date_folder_path, "Extracted")
                            os.makedirs(extract_folder, exist_ok=True)

                            with zipfile.ZipFile(renamed_zip_path, 'r') as zip_ref:
                                zip_ref.extractall(extract_folder)

                            remove_duplicate_files(date_folder_path, log_file)

                else:
                    st.warning("No ZIP files found. Retrying...")
                    retry_download()

            except Exception as e:
                st.error(f"An error occurred: {e}")
                retry_download()

            finally:
                driver.quit()

        main()
