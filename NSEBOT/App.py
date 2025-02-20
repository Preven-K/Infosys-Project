import os
import time
import zipfile
from datetime import datetime, timedelta
import streamlit as st
import matplotlib.pyplot as plt
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

# Global variables for login data and log messages
users = {"admin": "password"}  # Replace with secure storage in production
log_data = []

# Default download folder
DEFAULT_DOWNLOAD_FOLDER = os.path.expanduser("~/Downloads")

# Helper functions
def log_message(message):
    global log_data
    log_data.append(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}")
    print(message)
    with open("process_log.log", "a", encoding="utf-8") as log_file:
        log_file.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")

def find_and_process_zip():
    zip_filename = "Reports-Daily-Multiple.zip"
    print(f"Looking for {zip_filename} in {DEFAULT_DOWNLOAD_FOLDER}")
    zip_path = os.path.join(DEFAULT_DOWNLOAD_FOLDER, zip_filename)
    if not os.path.exists(zip_path):
        log_message(f"\u274C {zip_filename} not found in {DEFAULT_DOWNLOAD_FOLDER}")
        return False
    print(f"\u2705 Found {zip_filename} in {DEFAULT_DOWNLOAD_FOLDER}")

    log_message("Zip file downloaded and waiting for processing")

    today_date = datetime.now().strftime("%Y-%m-%d")
    base_folder = os.path.join(DEFAULT_DOWNLOAD_FOLDER, "NSE Reports", today_date)
    os.makedirs(base_folder, exist_ok=True)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(base_folder)
    os.remove(zip_path)
    print(f"\u2705 Extracted {zip_filename} to {base_folder}")
    log_message(f"\u2705 Extracted {zip_filename} to {base_folder}")

    process_and_segregate_files(base_folder)
    validate_files(base_folder)
    return True

def process_and_segregate_files(base_folder):
    ext_folders = {}
    log_file_path = os.path.join(base_folder, "Log.log")

    with open(log_file_path, "w", encoding="utf-8") as log_file:
        log_file.write(f"Process Log - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        log_file.write("-" * 50 + "\n")

        for root, dirs, files in os.walk(base_folder):
            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()

                if ext == ".zip":
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        zip_ref.extractall(base_folder)
                    os.remove(file_path)
                    log_file.write(f"\u2705 Extracted nested zip: {file}\n")
                    log_message(f"\u2705 Extracted nested zip: {file}")
                    process_and_segregate_files(base_folder)
                    continue

                if ext not in ext_folders:
                    ext_folder = os.path.join(base_folder, ext.lstrip('.').upper())
                    os.makedirs(ext_folder, exist_ok=True)
                    ext_folders[ext] = ext_folder

                target_path = os.path.join(ext_folders[ext], file)
                if not os.path.exists(target_path):
                    try:
                        os.rename(file_path, target_path)
                        log_file.write(f"\u2705 Moved: {file} -> {target_path}\n")
                        log_message(f"\u2705 Moved: {file} -> {target_path}")
                    except Exception as e:
                        log_file.write(f"❌ Error moving {file}: {e}\n")
                        log_message(f"❌ Error moving {file}: {e}")
                else:
                    try:
                        os.remove(file_path)
                        log_file.write(f"🗑️ Duplicate removed: {file}\n")
                        log_message(f"🗑️ Duplicate removed: {file}")
                    except Exception as e:
                        log_file.write(f"❌ Error removing duplicate {file}: {e}\n")
                        log_message(f"❌ Error removing duplicate {file}: {e}")

        log_file.write("-" * 50 + "\n")
        log_message(f"Process log saved at {log_file_path}")

def validate_files(base_folder):
    for root, dirs, files in os.walk(base_folder):
        for file in files:
            file_path = os.path.join(root, file)
            ext = os.path.splitext(file)[1].lower()
            if ext:
                ext_folder = os.path.join(base_folder, ext.lstrip('.').upper())
                target_path = os.path.join(ext_folder, file)
                if not os.path.exists(target_path):
                    log_message(f"❌ File {file} not moved to {ext_folder}")
                else:
                    log_message(f"✅ File {file} correctly moved to {ext_folder}")

def download_nse_reports():
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    #options.add_argument("--headless")
    service = Service(ChromeDriverManager().install())

    for attempt in range(3):
        try:
            log_message(f"Starting download attempt {attempt + 1}/3...")
            driver = webdriver.Chrome(service=service, options=options)
            driver.get("https://www.nseindia.com/all-reports")
            time.sleep(6)

            WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="Selectall"]/span'))
            ).click()
            print("✔️ Selected all reports.")
            log_message("✔️ Selected all reports.")
            time.sleep(6)

            WebDriverWait(driver, 18).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="MultiDwnld"]'))
            ).click()
            print("✔️ Clicked download button.")
            log_message("✔️ Clicked download button.")
            time.sleep(20)

            driver.quit()

            if find_and_process_zip():
                log_message("✅ Download and processing completed successfully.")
                return True
            else:
                log_message("❌ Zip file not found. Retrying...")
        except Exception as e:
            log_message(f"❌ Error during download: {e}")
        finally:
            try:
                driver.quit()
            except Exception as e:
                log_message(f"❌ Error while quitting driver: {e}")
    log_message("❌ All download attempts failed.")
    return False

def get_extension_summary(base_folder):
    ext_count = {}
    for root, dirs, files in os.walk(base_folder):
        for file in files:
            ext = os.path.splitext(file)[1]
            ext_count[ext] = ext_count.get(ext, 0) + 1
    return ext_count

def find_latest_folder(base_folder):
    date = datetime.now()
    while True:
        folder = os.path.join(base_folder, date.strftime("%Y-%m-%d"))
        if os.path.exists(folder):
            return folder, date.strftime("%Y-%m-%d")
        date -= timedelta(days=1)

def main_ui():
    st.sidebar.title("User Options")
    if st.sidebar.button("Logout"):
        st.session_state["authenticated"] = False
        st.experimental_rerun()

    if st.sidebar.button("Change Password"):
        change_password()

    st.image("https://placehold.co/600x100/black/gold?font=playfair-display&text=NSE-BOT%20 DASHBOARD", use_container_width=True)
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Manual Download")
        if st.button("Download Now"):
            if download_nse_reports():
                st.success("Reports downloaded and processed successfully!")
            else:
                st.error("Failed to download reports. Check the logs below.")

    with col2:
        st.subheader("Schedule Download")
        schedule_time = st.time_input("Select Time for Daily Download")
        if st.button("Set Schedule"):
            st.success(f"Download scheduled daily at {schedule_time}")
    
    st.subheader("Summary Pie Chart")
    base_folder = os.path.join(DEFAULT_DOWNLOAD_FOLDER, "NSE Reports")
    latest_folder, latest_date = find_latest_folder(base_folder)

    if latest_folder:
        ext_summary = get_extension_summary(latest_folder)
        if ext_summary:
            st.write(f"Date: {latest_date}")
            #st.write(f"File counts: {ext_summary}")
            labels, sizes = zip(*ext_summary.items())
            plt.figure(figsize=(6, 6))
            plt.pie(sizes, labels=labels, autopct=lambda p: f'{int(p * sum(sizes) / 100)}', startangle=140)
            plt.tight_layout()
            st.pyplot(plt)

            # Add space between the pie chart and the rows
            st.markdown("<br><br>", unsafe_allow_html=True)

            # Display file counts in a 4x2 grid
            cols = st.columns(3)
            for i, (ext, count) in enumerate(ext_summary.items()):
                with cols[i % 3]:
                    st.markdown(
                        f"""
                        <div style="background-color: black; color: white; padding: 10px; text-align: center;">
                            <h3>{ext}</h3>
                            <h4>{count}</h4>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
        else:
            st.info("No files to display in pie chart.")
    else:
        st.info("No folders found.")
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.subheader("Log Data")
    log_file_path = os.path.join(latest_folder, "Log.log")
    if os.path.exists(log_file_path):
        with open(log_file_path, "r", encoding="utf-8") as log_file:
            log_content = log_file.read()
        st.text_area("Logs", log_content, height=200)
    else:
        st.info("No logs available.")

def login():
    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username in users and users[username] == password:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Invalid username or password")

def signup():
    st.title("Signup")
    new_username = st.text_input("New Username")
    new_password = st.text_input("New Password", type="password")
    if st.button("Signup"):
        if new_username in users:
            st.error("Username already exists")
        else:
            users[new_username] = new_password
            st.success("User created successfully. Please login.")

def change_password():
    st.sidebar.title("Change Password")
    username = st.sidebar.text_input("Username")
    old_password = st.sidebar.text_input("Old Password", type="password")
    new_password = st.sidebar.text_input("New Password", type="password")
    if st.sidebar.button("Change Password"):
        if username in users and users[username] == old_password:
            users[username] = new_password
            st.sidebar.success("Password changed successfully")
        else:
            st.sidebar.error("Invalid username or old password")

# App execution logic
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    login()
    if st.button("Signup"):
        signup()
else:
    main_ui()