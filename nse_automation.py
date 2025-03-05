import streamlit as st
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import pandas as pd
import os
import pyodbc
import zipfile
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import schedule
from threading import Thread
import smtplib
import seaborn as sns
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
########################################################################################################################
# Global variables for login data and log messages
log_data = []

# Default download folder
today_date = datetime.today().strftime('%Y-%m-%d')
DEFAULT_DOWNLOAD_FOLDER = os.path.expanduser(f"~/Downloads")
DEFAULT_DOWNLOAD_FOLDER_Analysis = os.path.expanduser(f"~/Downloads/NSE Reports/{today_date}/CSV") # used for analysis
ANALYSIS_FOLDER = os.path.join(DEFAULT_DOWNLOAD_FOLDER_Analysis, 'Analysis')  # Folder to store analysis results

# Database connection
def get_db_connection():
    conn = pyodbc.connect(
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=PUVI-PREVEN-KS;'
        'DATABASE=NSEBOT_DB;'
        'Trusted_Connection=yes;'
    )
    return conn
########################################################################################################################
# Helper functions
def get_user_email(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT EMAIL FROM USER_LOGIN WHERE USER_ID = ?", (username,))
    email = cursor.fetchone()[0]
    conn.close()
    return email
########################################################################################################################
def log_message(message, log_file_path):
    global log_data
    log_data.append(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}")
    print(message)
    with open(log_file_path, "a", encoding="utf-8") as log_file:
        log_file.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
########################################################################################################################
def send_email_notification(to_email, subject, body, log_file_path, file_count=None, log_records=None, download_path=None, success=True):
    from_email = "prevenk.g3integeratedvlsi@gmail.com"
    from_password = "docg xsbg ujjt trwy"  # Use the app password generated from your Google account

    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject

    detailed_body = body
    if file_count is not None:
        detailed_body += f"\n\n📁 Total files processed: {file_count}"
    if log_records is not None:
        detailed_body += f"\n\n📝 Log Records:\n{log_records}"
    if download_path is not None:
        detailed_body += f"\n\n📂 Downloaded files are stored at: {download_path}"

    if not success:
        detailed_body += "\n\n❌ The download has failed. Please try scheduling again."
        detailed_body += "\n\n[Click here to login and schedule again](http://localhost:8501)"

    msg.attach(MIMEText(detailed_body, "plain"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(from_email, from_password)
        text = msg.as_string()
        server.sendmail(from_email, to_email, text)
        server.quit()
        log_message(f"✨ Email sent successfully to {to_email}: {subject}", log_file_path)
    except Exception as e:
        log_message(f"Failed to send email to {to_email}: {e}", log_file_path)
        print(f"Failed to send email to {to_email}: {e}")
########################################################################################################################
def find_and_process_zip(log_file_path):
    zip_filename = "Reports-Daily-Multiple.zip"
    zip_path = os.path.join(DEFAULT_DOWNLOAD_FOLDER, zip_filename)
    if not os.path.exists(zip_path):
        log_message(f"\u274C {zip_filename} not found in {DEFAULT_DOWNLOAD_FOLDER}", log_file_path)
        return False

    log_message("Zip file downloaded and waiting for processing", log_file_path)

    today_date = datetime.now().strftime("%Y-%m-%d")
    base_folder = os.path.join(DEFAULT_DOWNLOAD_FOLDER, "NSE Reports", today_date)
    os.makedirs(base_folder, exist_ok=True)

    extract_zip(zip_path, base_folder, log_file_path)
    process_nested_zips(base_folder, log_file_path)
    check_and_remove_duplicates(base_folder, log_file_path)
    segregate_files(base_folder, log_file_path)
    validate_files(base_folder, log_file_path)
    return True
########################################################################################################################
def extract_zip(zip_path, extract_to, log_file_path):
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        os.remove(zip_path)
        log_message(f"📍 Extracted {zip_path} to {extract_to}", log_file_path)
    except Exception as e:
        log_message(f"⚠️ Error extracting {zip_path}: {e}", log_file_path)
########################################################################################################################
def process_nested_zips(base_folder, log_file_path):
    for root, dirs, files in os.walk(base_folder):
        for file in files:
            file_path = os.path.join(root, file)
            if file_path.endswith(".zip"):
                extract_zip(file_path, base_folder, log_file_path)
                process_nested_zips(base_folder, log_file_path)
########################################################################################################################
def check_and_remove_duplicates(base_folder, log_file_path):
    seen_files = set()
    for root, dirs, files in os.walk(base_folder):
        for file in files:
            file_path = os.path.join(root, file)
            if file in seen_files:
                os.remove(file_path)
                log_message(f"🗑️ Duplicate removed: {file}", log_file_path)
            else:
                seen_files.add(file)
########################################################################################################################
def segregate_files(base_folder, log_file_path):
    ext_folders = {}
    for root, dirs, files in os.walk(base_folder):
        for file in files:
            file_path = os.path.join(root, file)
            ext = os.path.splitext(file)[1].lower()
            if ext:
                if ext not in ext_folders:
                    ext_folder = os.path.join(base_folder, ext.lstrip('.').upper())
                    os.makedirs(ext_folder, exist_ok=True)
                    ext_folders[ext] = ext_folder

                target_path = os.path.join(ext_folders[ext], file)
                if not os.path.exists(target_path):
                    try:
                        os.rename(file_path, target_path)
                        log_message(f"📍 Moved: {file} -> {target_path}", log_file_path)
                    except Exception as e:
                        log_message(f"❌ Error moving {file}: {e}", log_file_path)
########################################################################################################################
def validate_files(base_folder, log_file_path):
    for root, dirs, files in os.walk(base_folder):
        for file in files:
            file_path = os.path.join(root, file)
            ext = os.path.splitext(file)[1].lower()
            if ext:
                ext_folder = os.path.join(base_folder, ext.lstrip('.').upper())
                target_path = os.path.join(ext_folder, file)
                if not os.path.exists(target_path):
                    log_message(f"❌ File {file} not moved to {ext_folder}", log_file_path)
                else:
                    log_message(f"✅ ✨File {file} correctly moved to {ext_folder}", log_file_path)
########################################################################################################################
def download_nse_reports(email=None):
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-extensions")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3")
    service = Service(ChromeDriverManager().install())

    today_date = datetime.now().strftime("%Y-%m-%d")
    base_folder = os.path.join(DEFAULT_DOWNLOAD_FOLDER, "NSE Reports", today_date)
    os.makedirs(base_folder, exist_ok=True)
    log_file_path = os.path.join(base_folder, "Log.log")

    progress_bar = st.progress(0)
    for attempt in range(5):
        try:
            log_message(f"Starting download attempt {attempt + 1}/5...", log_file_path)
            driver = webdriver.Chrome(service=service, options=options)
            driver.get("https://www.nseindia.com/all-reports")
            time.sleep(5)

            WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="Selectall"]/span'))
            ).click()

            log_message("✔️ Selected all reports.", log_file_path)
            time.sleep(3)

            WebDriverWait(driver, 18).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="MultiDwnld"]'))
            ).click()
            log_message("✔️ Clicked download button.", log_file_path)
            time.sleep(20)

            driver.quit()

            if find_and_process_zip(log_file_path):
                log_message("✨ Download and processing completed successfully.", log_file_path)
                progress_bar.progress(100)
                ext_summary = get_extension_summary(base_folder)
                file_count = sum(ext_summary.values())
                log_records = "\n".join(log_data[-5:])  # Last 5 log records
                if email:
                    send_email_notification(
                        email,
                        "Download Completed",
                        "The scheduled download has been completed successfully.✨",
                        log_file_path,
                        file_count=file_count,
                        log_records=log_records,
                        download_path=base_folder,
                        success=True
                    )
                return True
            else:
                log_message("❌ Zip file not found. Retrying...", log_file_path)
        except Exception as e:
            log_message(f"❌ Error during download: {e}", log_file_path)
        finally:
            try:
                driver.quit()
            except Exception as e:
                log_message(f"❌ Error while quitting driver: {e}", log_file_path)
        progress_bar.progress((attempt + 1) * 20)
    log_message("❌ All download attempts failed.", log_file_path)
    if email:
        send_email_notification(
            email,
            "Download Failed",
            "The scheduled download has failed. Please check the logs.",
            log_file_path,
            success=False
        )
    return False
########################################################################################################################
def get_extension_summary(base_folder):
    ext_count = {}
    for root, dirs, files in os.walk(base_folder):
        for file in files:
            ext = os.path.splitext(file)[1]
            ext_count[ext] = ext_count.get(ext, 0) + 1
    return ext_count
########################################################################################################################
def find_latest_folder(base_folder):
    date = datetime.now()
    while True:
        folder = os.path.join(base_folder, date.strftime("%Y-%m-%d"))
        if os.path.exists(folder):
            return folder, date.strftime("%Y-%m-%d")
        date -= timedelta(days=1)
        if date.year < 2000:  # Prevent infinite loop
            break
    return None, None
########################################################################################################################

def save_custom_theme(sidebar_image_url, main_ui_image_url, sidebar_color, main_ui_color):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        MERGE INTO USER_THEME AS target
        USING (SELECT ? AS USER_ID, ? AS SIDEBAR_IMAGE_URL, ? AS MAIN_UI_IMAGE_URL, ? AS SIDEBAR_COLOR, ? AS MAIN_UI_COLOR) AS source
        ON target.USER_ID = source.USER_ID
        WHEN MATCHED THEN
            UPDATE SET SIDEBAR_IMAGE_URL = source.SIDEBAR_IMAGE_URL, MAIN_UI_IMAGE_URL = source.MAIN_UI_IMAGE_URL, SIDEBAR_COLOR = source.SIDEBAR_COLOR, MAIN_UI_COLOR = source.MAIN_UI_COLOR
        WHEN NOT MATCHED THEN
            INSERT (USER_ID, SIDEBAR_IMAGE_URL, MAIN_UI_IMAGE_URL, SIDEBAR_COLOR, MAIN_UI_COLOR) VALUES (source.USER_ID, source.SIDEBAR_IMAGE_URL, source.MAIN_UI_IMAGE_URL, source.SIDEBAR_COLOR, source.MAIN_UI_COLOR);
    """, (st.session_state["username"], sidebar_image_url, main_ui_image_url, sidebar_color, main_ui_color))
    conn.commit()
    conn.close()
########################################################################################################################
def get_custom_theme():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT SIDEBAR_IMAGE_URL, MAIN_UI_IMAGE_URL, SIDEBAR_COLOR, MAIN_UI_COLOR FROM USER_THEME WHERE USER_ID = ?", (st.session_state["username"],))
    theme = cursor.fetchone()
    conn.close()
    return theme
########################################################################################################################
def main_ui():
    global DEFAULT_DOWNLOAD_FOLDER

    st.sidebar.title("Settings")
    theme = st.sidebar.selectbox("Select Theme", ["dark", "default", "light","Customized"], key="theme_selectbox")
    if theme == "default":
        #  background-image: url("https://wallpapercave.com/wp/PCeSceh.jpg");
        # background-image: url("https://wallpapercave.com/wp/wp3075809.jpg");

        css = """
        <style>
        [data-testid="stAppViewContainer"] {
            background-image: url("https://wallpapercave.com/wp/PCeSceh.jpg");
            background-size: cover;
            background-repeat: no-repeat;
            background-attachment: fixed;
            background-position: center center;
        }
        [data-testid="stHeader"] {
            background-color: rgba(0, 0, 0, 0);
        }
        [data-testid="stSidebar"] {
            background-image: url("https://i.pinimg.com/originals/82/02/48/820248c81542b70518a5d65f444ea86f.jpg");
            background-size: cover;
            background-repeat: no-repeat;
            background-position: center center;
            
        }
        [data-testid="stToolbar"] {
            right: 2rem;
        }
        </style>
        """
    elif theme == "dark":
        css = """
        <style>
        [data-testid="stAppViewContainer"] {
            background-color: #1e1e1e;
            color: white;
        }
        [data-testid="stHeader"] {
            background-color: rgba(30, 30, 30, 0.8);
            color: white;
        }
        [data-testid="stSidebar"] {
            background-color: #black;
            color: white;
        }
        [data-testid="stToolbar"] {
            right: 2rem;
        }
        input, select, textarea {
            background-color: white;
            color: black;
        }
        </style>
        """
    elif theme == "light":
        css = """
        <style>
        [data-testid="stAppViewContainer"] {
            background-color: #87CEEB;
            color: black;
        }
        [data-testid="stHeader"] {
            background-color: rgba(135, 206, 235, 0.8);
            color: black;
        }
        [data-testid="stSidebar"] {
            background-color: #4682B4;
            color: black;
        }
        [data-testid="stToolbar"] {
            right: 2rem;
        }
        input, select, textarea {
            background-color: black;
            color: black;
        }
        
        /* More specific selector */
        div[data-testid="stTextInput"] label p {
            color: black !important;
        }
        div[data-testid="stSelectbox"] label p {
            color: black !important;
        }
        div[data-testid="stCheckbox"] label p {
           color: black !important;
        }
        div[data-testid="stColorPicker"] label p {
           color: black !important;
        }
        }
        </style>
        """
    elif theme == "Customized":
        custom_theme = get_custom_theme()
        if custom_theme:
            sidebar_image_url, main_ui_image_url, sidebar_color, main_ui_color = custom_theme
            css = f"""
            <style>
            [data-testid="stAppViewContainer"] {{
                background-image: url("{main_ui_image_url}");
                background-color: {main_ui_color};
                color: white;
            }}
            [data-testid="stHeader"] {{
                background-color: rgba(135, 206, 235, 0.8);
                color: white;
            }}
            [data-testid="stSidebar"] {{
                background-image: url("{sidebar_image_url}");
                background-color: {sidebar_color};
                color: white;
            }}
            [data-testid="stToolbar"] {{
                right: 2rem;
            }}
            input, select, textarea {{
                background-color: white;
                color: white;
            }}
            div.stButton > button {{
                background-color: #ff0000;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
            }}
            div.stButton > button:hover {{
                background-color: #cc0000;
            }}
            </style>
            """
        else:
            st.error("No custom theme found. Please set your custom theme in the Customization tab.")
            css = ""

    st.markdown(css, unsafe_allow_html=True)

    if st.sidebar.button("Logout", key="logout_button"):
        st.session_state["authenticated"] = False
        st.rerun()

    st.image("https://placehold.co/600x100/black/gold?font=playfair-display&text=NSE-BOT%20 DASHBOARD", use_container_width=True)
    st.markdown("<br><br>", unsafe_allow_html=True)

    # Tabs for main UI
    tabs = st.tabs(["Home", "Summary","Settings","Customise","Analytics"])
    with tabs[0]:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Manual Download 📥")
            if st.button("Download Now", key="download_now_button"):
                if download_nse_reports():
                    st.success("Reports downloaded and processed successfully!")
                else:
                    st.error("Failed to download reports. Check the logs below.")

        with col2:
            st.subheader("Schedule Download 📅")
            previous_schedule = get_previous_schedule()
            common_times = [f"{hour:02d}:{minute:02d}" for hour in range(24) for minute in range(0, 60, 15)]
            if previous_schedule:
                try:
                    schedule_time_index = common_times.index(previous_schedule[0])
                except ValueError:
                    schedule_time_index = 0
            else:
                schedule_time_index = 0
            schedule_time = st.selectbox("Select Time for Daily Download", common_times, key="schedule_time_selectbox", index=schedule_time_index)
            custom_time = st.checkbox("Not found in the list? Enter custom time", key="custom_time_checkbox")
            if custom_time:
                schedule_time = st.text_input("Enter Time for Daily Download (HH:MM)", key="custom_schedule_time_input")
            use_registered_email = st.checkbox("Use registered email for notifications", key="use_registered_email_checkbox")
            if use_registered_email:
                email = get_user_email(st.session_state["username"])
            else:
                email = st.text_input("Enter your email for notifications", key="email_schedule_input", value=previous_schedule[1] if previous_schedule else "")
            if st.button("Set Schedule", key="set_schedule_button"):
                try:
                    datetime.strptime(schedule_time, "%H:%M")
                    log_file_path = os.path.join(DEFAULT_DOWNLOAD_FOLDER, "NSE Reports", "Log.log")
                    schedule_daily_download(schedule_time, email, log_file_path)
                    st.success(f"Download scheduled daily at {schedule_time}")
                except ValueError:
                    st.error("Invalid time format. Please enter time in HH:MM format.")
            
            if previous_schedule:
                st.markdown(
                    f"""
                    <div style="background-color: #ff0000;
                      padding: 10px; 
                      border-radius: 5px; 
                      border: 1px solid #cc0000;
                      color: white;">
                        <strong>Previous Schedule:</strong> {previous_schedule[0]}<br>
                        <strong>Email:</strong> {previous_schedule[1]}
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        st.markdown("---")
        # Summary section
    with tabs[1]:
        st.subheader("Summary Pie Chart")
        base_folder = os.path.join(DEFAULT_DOWNLOAD_FOLDER, "NSE Reports")
        latest_folder, latest_date = find_latest_folder(base_folder)

        if latest_folder:
            ext_summary = get_extension_summary(latest_folder)
            if ext_summary:
                st.write(f"Date: {latest_date}")
                labels, sizes = zip(*ext_summary.items())
                plt.figure(figsize=(6, 6))
                plt.pie(sizes, labels=labels, autopct=lambda p: f'{int(p * sum(sizes) / 100)}', startangle=140)
                plt.tight_layout()
                st.pyplot(plt)

                st.markdown("<br><br>", unsafe_allow_html=True)

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
        st.markdown("---")
        st.subheader("Log Data")
        if latest_folder:
            log_file_path = os.path.join(latest_folder, "Log.log")
            if os.path.exists(log_file_path):
                with open(log_file_path, "r", encoding="utf-8") as log_file:
                    log_content = log_file.read()
                st.text_area("Logs", log_content, height=200, key="log_content_text_area")
            else:
                st.info("No logs available.")
        else:
            st.info("No logs available.")

    with tabs[2]:
        st.subheader("Change Email ID")

        # Email ID change
        current_email = st.text_input("Enter current email ID", key="current_email_input")
        new_email = st.text_input("Enter new email ID", key="new_email_input")
        confirm_new_email = st.text_input("Confirm new email ID", key="confirm_new_email_input")
        if st.button("Change Email ID", key="change_email_button"):
            if new_email != confirm_new_email:
                st.error("New email IDs do not match")
            else:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM USER_LOGIN WHERE USER_ID = ? AND EMAIL = ?", (st.session_state["username"], current_email))
                user = cursor.fetchone()
                if user:
                    cursor.execute("UPDATE USER_LOGIN SET EMAIL = ? WHERE USER_ID = ?", (new_email, st.session_state["username"]))
                    conn.commit()
                    st.success("Email ID changed successfully")
                else:
                    st.error("Current email ID is incorrect")
                conn.close()
        st.markdown("---")

        # Change Password
        st.subheader("Change Password")
        old_password = st.text_input("Old Password", type="password", key="change_password_old_password_input")
        new_password = st.text_input("New Password", type="password", key="change_password_new_password_input")
        if st.button("Change Password", key="change_password_button"):
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM USER_LOGIN WHERE USER_ID = ? AND PASSWORD = ?", (st.session_state["username"], old_password))
            user = cursor.fetchone()
            if user:
                cursor.execute("UPDATE USER_LOGIN SET PASSWORD = ? WHERE USER_ID = ?", (new_password, st.session_state["username"]))
                conn.commit()
                st.success("Password changed successfully")
            else:
                st.error("Invalid username or old password")
            conn.close()
        st.markdown("---")

        # Delete Account  
        st.subheader("Delete Account")  
        st.markdown("""
            <style>
            div.stButton > button {
                background-color: red;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
            }
            div.stButton > button:hover {
                background-color: darkred;
            }
            </style>
            """, unsafe_allow_html=True)        
        if st.button("Delete Account", key="delete_account_button"):
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM USER_LOGIN WHERE USER_ID = ?", (st.session_state["username"],))
            conn.commit()
            conn.close()
            st.success("Account deleted successfully")
            st.session_state["authenticated"] = False
            st.rerun()
        st.markdown("---")
    with tabs[3]:
        st.subheader("Customization")
        sidebar_image_url = st.text_input("Sidebar Image URL", key="sidebar_image_url")
        main_ui_image_url = st.text_input("Main UI Image URL", key="main_ui_image_url")
        sidebar_color = st.color_picker("Sidebar Background Color", key="sidebar_color")
        main_ui_color = st.color_picker("Main UI Background Color", key="main_ui_color")
        if st.button("Save Custom Theme", key="save_custom_theme_button"):
            save_custom_theme(sidebar_image_url, main_ui_image_url, sidebar_color, main_ui_color)
            st.success("Custom theme saved successfully")
    with tabs[4]:
        
        analyze_csv(file_path=DEFAULT_DOWNLOAD_FOLDER)
########################################################################################################################
def create_analysis_log(log_file_path, message):
    """
    Create or append to the Data Analysis Log file.
    """
    with open(log_file_path, "a", encoding="utf-8") as log_file:
        log_file.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
########################################################################################################################
def analyze_csv(file_path, recursion=False):
    if not recursion:
        st.subheader("Stock Analysis")

        # Add a "Start Analysis" button
        if st.button("Start Analysis", key="start_analysis_button"):
            # Run analysis and store results in session state
            st.session_state["analysis_results"] = analyze_files_separately(DEFAULT_DOWNLOAD_FOLDER_Analysis)
            st.success("Analysis completed successfully!")

        # Check if analysis results are available in session state
        if "analysis_results" not in st.session_state:
            st.info("Click 'Start Analysis' to begin the analysis process.")
            return

        # Retrieve results from session state
        buy_prices, sell_prices, top_amt, top_qty, top_short_qty, columns = st.session_state["analysis_results"]

        # Add a unique key to the selectbox
        category = st.selectbox(
            "Select Analysis Category",
            ["Top Buy Stocks", "Top Sold Stocks", "Highest Quantity", "Highest Amount"],
            key="analysis_category_selectbox"
        )

        # Display results based on the selected category
        if category == "Top Buy Stocks":
            if not buy_prices.empty:
                st.title("Top Buy Stocks")


                # Create visualization
                fig, ax = plt.subplots(figsize=(10, 6))
                # Assign unique colors for each bar
                unique_names = buy_prices[buy_prices.columns[0]].unique()
                color_palette = sns.color_palette("husl", len(unique_names))
                color_dict = {name: color_palette[i % len(color_palette)] for i, name in enumerate(unique_names)}
                colors = [color_dict[name] for name in buy_prices[buy_prices.columns[0]]]

                sns.barplot(data=buy_prices, x=buy_prices.columns[1], y=buy_prices.columns[0], ax=ax, palette=colors)
                plt.title("Top 5 Buy Stocks")
                st.pyplot(fig)

                # Reset index 
                buy_prices = buy_prices.reset_index(drop=True)
                st.write(buy_prices)
            else:
                st.info("No data available for Top 5 Buy Stocks")

        elif category == "Top Sold Stocks":
            if not sell_prices.empty:
                st.title("Top Sold Stocks")


                # Create visualization
                fig, ax = plt.subplots(figsize=(10, 6))
                # Assign unique colors for each bar
                unique_names = sell_prices[sell_prices.columns[0]].unique()
                color_palette = sns.color_palette("husl", len(unique_names))
                color_dict = {name: color_palette[i % len(color_palette)] for i, name in enumerate(unique_names)}
                colors = [color_dict[name] for name in sell_prices[sell_prices.columns[0]]]

                sns.barplot(data=sell_prices, x=sell_prices.columns[1], y=sell_prices.columns[0], ax=ax, palette=colors)
                plt.title("Top 5 Sold Stocks")
                st.pyplot(fig)

                # Reset index 
                sell_prices = sell_prices.reset_index(drop=True)
                st.write(sell_prices)
            else:
                st.info("No data available for Top 5 Sold Stocks")

        elif category == "Highest Quantity":
            if not top_qty.empty:
                st.title("Highest Quantity")

                # Aggregate quantities for stocks with the same name
                aggregated_qty = top_qty.groupby(top_qty.columns[0])[top_qty.columns[1]].sum().reset_index()
                aggregated_qty.columns = ["Stock Name", "Total Quantity"]

                # Sort by total quantity in descending order
                aggregated_qty = aggregated_qty.sort_values(by="Total Quantity", ascending=False)
                # Select top 5 for the bar chart
                top_5_qty = aggregated_qty.head(5)
                # Print the top 5 DataFrame

                # Display the bar chart
                fig, ax = plt.subplots(figsize=(10, 6))
                sns.barplot(data=top_5_qty, x="Total Quantity", y="Stock Name", ax=ax, palette="viridis")
                plt.title("Top 5 Stocks by Quantity")
                st.pyplot(fig)

                st.write(top_5_qty)
            else:
                st.info("No data available for Highest Quantity")
        
        elif category == "Highest Amount":
            if not top_amt.empty:
                st.title("Highest Amount")


                # Create visualization
                fig, ax = plt.subplots(figsize=(10, 6))
                # Assign unique colors for each bar
                unique_names = top_amt[top_amt.columns[0]].unique()
                color_palette = sns.color_palette("husl", len(unique_names))
                color_dict = {name: color_palette[i % len(color_palette)] for i, name in enumerate(unique_names)}
                colors = [color_dict[name] for name in top_amt[top_amt.columns[0]]]

                sns.barplot(data=top_amt, x=top_amt.columns[1], y=top_amt.columns[0], ax=ax, palette=colors)
                plt.title("5 Highest Amount")
                st.pyplot(fig)

                                # Reset index and display without S.No
                top_amt = top_amt.reset_index(drop=True)
                st.write(top_amt)
            else:
                st.info("No data available for 5 Highest Amount")

    # Recursive call logic
    else:
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), None

        try:
            # Read the CSV file, skipping bad lines
            df = pd.read_csv(file_path, on_bad_lines='skip')
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), None

        # Drop duplicate columns
        df = df.loc[:, ~df.columns.duplicated()]

        # Identify the required columns based on keywords
        name_col = None
        buy_sell_col = None
        price_col = None
        qty_col = None
        amt_col = None

        for col in df.columns:
            if 'client' in col.lower() or ('name' in col.lower() or 'symbol' in col.lower() or 'security' in col.lower()):
                name_col = col
            elif 'buy/sell' in col.lower() or 'transaction' in col.lower():
                buy_sell_col = col
            elif 'price' in col.lower() or 'trade price' in col.lower() or 'wght. avg. price' in col.lower():
                price_col = col
            elif 'qty' in col.lower() or 'quantity' in col.lower() or 'quantity traded' in col.lower():
                qty_col = col
            elif 'amt' in col.lower() or 'amount' in col.lower() or 'amt fin by all the members' in col.lower():
                amt_col = col

        # Check for column names inside the rows
        if not (name_col and (buy_sell_col and price_col) or (qty_col and amt_col and name_col) or ((name_col) and (qty_col or 'qty' in df.columns) and (price_col or amt_col))):
            for i, row in df.iterrows():
                if 'name' in row.astype(str).str.lower().values or 'qty' in row.astype(str).str.lower().values or 'amt' in row.astype(str).str.lower().values or 'security name' in row.astype(str).str.lower().values:
                    df.columns = row
                    df = df.drop(i)
                    break

            for col in df.columns:
                if 'client' in col.lower() or ('name' in col.lower() or 'symbol' in col.lower() or 'security' in col.lower()):
                    name_col = col
                elif 'buy/sell' in col.lower() or 'transaction' in col.lower():
                    buy_sell_col = col
                elif 'price' in col.lower() or 'trade price' in col.lower() or 'wght. avg. price' in col.lower():
                    price_col = col
                elif 'qty' in col.lower() or 'quantity' in col.lower() or 'quantity traded' in col.lower():
                    qty_col = col
                elif 'amt' in col.lower() or 'amount' in col.lower() or 'amt fin by all the members' in col.lower():
                    amt_col = col

        if not (name_col and (buy_sell_col and price_col) or (qty_col and amt_col and name_col) or ((name_col) and (qty_col or 'qty' in df.columns) and (price_col or amt_col))):
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), df.columns.tolist()

        # Convert 'Buy/Sell' column to string and normalize if it exists
        if buy_sell_col:
            df[buy_sell_col] = df[buy_sell_col].astype(str).str.strip().str.upper()

        # Filter buy and sell prices if columns exist
        buy_prices = pd.DataFrame()
        sell_prices = pd.DataFrame()
        if buy_sell_col and price_col:
            buy_prices = df[df[buy_sell_col] == 'BUY'][[name_col, price_col, qty_col]].sort_values(by=price_col, ascending=False).head(5)
            sell_prices = df[df[buy_sell_col] == 'SELL'][[name_col, price_col, qty_col]].sort_values(by=price_col, ascending=True).head(5)

        # Find top 5 amounts and quantities if columns exist
        top_amt = pd.DataFrame()
        top_qty = pd.DataFrame()
        if amt_col and name_col:
            top_amt = df[[name_col, amt_col]].sort_values(by=amt_col, ascending=False).head(5)
        if qty_col and name_col:
            top_qty = df[[name_col, qty_col]].sort_values(by=qty_col, ascending=False).head(5)

        # Find top 5 quantities and corresponding security names for shortselling
        top_short_qty = pd.DataFrame()
        if name_col and qty_col:
            top_short_qty = df[[name_col, qty_col]].sort_values(by=qty_col, ascending=False).head(5)

        return buy_prices, sell_prices, top_amt, top_qty, top_short_qty, None
####################################################################################################

def analyze_files_separately(directory):
    column_info = []
    all_buy_prices = pd.DataFrame()
    all_sell_prices = pd.DataFrame()
    all_top_amt = pd.DataFrame()
    all_top_qty = pd.DataFrame()
    all_top_short_qty = pd.DataFrame()

    # Ensure the ANALYSIS_FOLDER exists
    os.makedirs(ANALYSIS_FOLDER, exist_ok=True)

    # Create the Data Analysis Log file
    log_file_path = os.path.join(ANALYSIS_FOLDER, "data_analysis_log.txt")
    create_analysis_log(log_file_path, "Starting Data Analysis Process")

    for filename in os.listdir(directory):
        if filename.endswith(".csv"):
            file_path = os.path.join(directory, filename)
            create_analysis_log(log_file_path, f"Processing file: {filename}")

            try:
                df = pd.read_csv(file_path, on_bad_lines='skip')
                buy_prices, sell_prices, top_amt, top_qty, top_short_qty, columns = analyze_csv(file_path, recursion=True)

                if not buy_prices.empty or not sell_prices.empty or not top_amt.empty or not top_qty.empty or not top_short_qty.empty:
                    all_buy_prices = pd.concat([all_buy_prices, buy_prices])
                    all_sell_prices = pd.concat([all_sell_prices, sell_prices])
                    all_top_amt = pd.concat([all_top_amt, top_amt])
                    all_top_qty = pd.concat([all_top_qty, top_qty])
                    all_top_short_qty = pd.concat([all_top_short_qty, top_short_qty])
                    create_analysis_log(log_file_path, f"✅ Successfully processed file: {filename}")
                    print(f"✅ Successfully processed file: {filename}")
                elif columns is not None:
                    column_info.append((filename, ', '.join(columns)))
                    create_analysis_log(log_file_path, f"✅File {filename} does not contain the required columns.")
                    print(f"❌ File {filename} does not contain the required columns. Columns found: {columns}")

            except pd.errors.ParserError as e:
                create_analysis_log(log_file_path, f"Error reading {filename}: {e}")
                print(f"Error reading {filename}: {e}")
                continue

    # Save column information to a text file in table format
    with open(os.path.join(ANALYSIS_FOLDER, 'column_info.txt'), 'w') as f:
        f.write(f"{'File Name':<30} | Columns\n")
        f.write(f"{'-'*30} | {'-'*50}\n")
        for info in column_info:
            f.write(f"{info[0]:<30} | {info[1]}\n")

    # Reset index for all DataFrames to avoid duplicate labels
    all_buy_prices = all_buy_prices.reset_index(drop=True)
    all_sell_prices = all_sell_prices.reset_index(drop=True)
    all_top_amt = all_top_amt.reset_index(drop=True)
    all_top_qty = all_top_qty.reset_index(drop=True)
    all_top_short_qty = all_top_short_qty.reset_index(drop=True)

    create_analysis_log(log_file_path, "Data Analysis Process Completed")
    return all_buy_prices, all_sell_prices, all_top_amt, all_top_qty, all_top_short_qty, column_info

########################################################################################################################
def plot_prices(buy_prices, sell_prices, top_amt, top_qty, top_short_qty):
    sns.set_theme(style="whitegrid")

    fig, ax = plt.subplots(5, 1, figsize=(12, 24))

    # Reset index for all DataFrames to avoid duplicate labels
    buy_prices = buy_prices.reset_index(drop=True)
    sell_prices = sell_prices.reset_index(drop=True)
    top_amt = top_amt.reset_index(drop=True)
    top_qty = top_qty.reset_index(drop=True)
    top_short_qty = top_short_qty.reset_index(drop=True)

    # Plot top 5 buy prices
    if not buy_prices.empty:
        sns.barplot(x=buy_prices[buy_prices.columns[1]], y=buy_prices[buy_prices.columns[0]], ax=ax[0], palette="Greens_d")
        ax[0].set_title('Top 5 Buy Prices')
        ax[0].set_xlabel('Trade Price')
        ax[0].set_ylabel('Stock Name')
        for i in ax[0].containers:
            ax[0].bar_label(i,)
    else:
        ax[0].text(0.5, 0.5, 'No data available', horizontalalignment='center', verticalalignment='center')
        ax[0].set_title('Top Buy Prices')

    # Plot top 5 sell prices
    if not sell_prices.empty:
        sns.barplot(x=sell_prices[sell_prices.columns[1]], y=sell_prices[sell_prices.columns[0]], ax=ax[1], palette="Reds_d")
        ax[1].set_title('Top Sell Prices')
        ax[1].set_xlabel('Trade Price')
        ax[1].set_ylabel('Stock Name')
        for i in ax[1].containers:
            ax[1].bar_label(i,)
    else:
        ax[1].text(0.5, 0.5, 'No data available', horizontalalignment='center', verticalalignment='center')
        ax[1].set_title('Top 5 Sell Prices')

    # Plot top 5 amounts
    if not top_amt.empty:
        sns.barplot(x=top_amt[top_amt.columns[1]], y=top_amt[top_amt.columns[0]], ax=ax[2], palette="Blues_d")
        ax[2].set_title('Top Amounts')
        ax[2].set_xlabel('Amount (Rs. In Lakhs)')
        ax[2].set_ylabel('Stock Name')
        for i in ax[2].containers:
            ax[2].bar_label(i,)
    else:
        ax[2].text(0.5, 0.5, 'No data available', horizontalalignment='center', verticalalignment='center')
        ax[2].set_title('Top 5 Amounts')

    # Plot top 5 quantities
    if not top_qty.empty:
        sns.barplot(x=top_qty[top_qty.columns[1]], y=top_qty[top_qty.columns[0]], ax=ax[3], palette="Purples_d")
        ax[3].set_title('Top 5 Quantities')
        ax[3].set_xlabel('Quantity (No. of Shares)')
        ax[3].set_ylabel('Stock Name')
        for i in ax[3].containers:
            ax[3].bar_label(i,)
    else:
        ax[3].text(0.5, 0.5, 'No data available', horizontalalignment='center', verticalalignment='center')
        ax[3].set_title('Top 5 Quantities')

    # Plot top 5 shortselling quantities
    if not top_short_qty.empty:
        sns.barplot(x=top_short_qty[top_short_qty.columns[1]], y=top_short_qty[top_short_qty.columns[0]], ax=ax[4], palette="Oranges_d")
        ax[4].set_title('Top 5 Shortselling Quantities')
        ax[4].set_xlabel('Quantity (No. of Shares)')
        ax[4].set_ylabel('Stock Name')
        for i in ax[4].containers:
            ax[4].bar_label(i,)
    else:
        ax[4].text(0.5, 0.5, 'No data available', horizontalalignment='center', verticalalignment='center')
        ax[4].set_title('Top 5 Shortselling Quantities')

    plt.tight_layout()
    st.pyplot(fig)

########################################################################################################################

def find_latest_folder(base_folder, days_back=0):
    date = datetime.now() - timedelta(days=days_back)
    while True:
        folder = os.path.join(base_folder, date.strftime("%Y-%m-%d"))
        if os.path.exists(folder):
            return folder, date.strftime("%Y-%m-%d")
        date -= timedelta(days=1)
        if date.year < 2000:  # Prevent infinite loop
            break
    return None, None
########################################################################################################################
def schedule_daily_download(schedule_time, email, log_file_path):
    def job():
        success = download_nse_reports(email)
        if success:
            send_email_notification(email, "Download Completed", "The scheduled download has been completed successfully.✨", log_file_path)
        else:
            send_email_notification(email, "Download Failed", "The scheduled download has failed. Please check the logs.", log_file_path)

    schedule.every().day.at(schedule_time).do(job)

    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(1)

    scheduler_thread = Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()

    # Save the schedule to the database using MERGE
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        MERGE INTO SCHEDULE AS target
        USING (SELECT ? AS USER_ID, ? AS SCHEDULE_TIME, ? AS EMAIL) AS source
        ON target.USER_ID = source.USER_ID
        WHEN MATCHED THEN
            UPDATE SET SCHEDULE_TIME = source.SCHEDULE_TIME, EMAIL = source.EMAIL
        WHEN NOT MATCHED THEN
            INSERT (USER_ID, SCHEDULE_TIME, EMAIL) VALUES (source.USER_ID, source.SCHEDULE_TIME, source.EMAIL);
    """, (st.session_state["username"], schedule_time, email))
    conn.commit()
    conn.close()
########################################################################################################################

def get_previous_schedule():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT SCHEDULE_TIME, EMAIL FROM SCHEDULE WHERE USER_ID = ?", (st.session_state["username"],))
    schedule = cursor.fetchone()
    conn.close()
    return schedule
########################################################################################################################
def login():
    st.title("Login")
    identifier = st.text_input("Username or Email", key="login_identifier")
    password = st.text_input("Password", type="password", key="login_password")
    if st.button("Login", key="login_button"):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM USER_LOGIN WHERE (USER_ID = ? OR EMAIL = ?) AND PASSWORD = ?", (identifier, identifier, password))
        user = cursor.fetchone()
        conn.close()
        if user:
            st.session_state["authenticated"] = True
            st.session_state["username"] = user[0]  # Store the username in session state
            st.rerun()
        else:
            st.error("Invalid username/email or password")
########################################################################################################################
def signup():
    st.title("Signup")
    new_username = st.text_input("New Username", key="signup_username")
    new_password = st.text_input("New Password", type="password", key="signup_password")
    new_email = st.text_input("Email ID", key="signup_email")
    if st.button("Signup", key="signup_button"):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM USER_LOGIN WHERE USER_ID = ?", (new_username,))
        user = cursor.fetchone()
        if user:
            st.error("Username already exists")
        else:
            cursor.execute("INSERT INTO USER_LOGIN (USER_ID, PASSWORD, EMAIL) VALUES (?, ?, ?)", (new_username, new_password, new_email))
            conn.commit()
            st.success("User created successfully. Please login.")
        conn.close()

########################################################################################################################
# App execution logic
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.image("https://placehold.co/600x200/black/gold?font=playfair-display&text=NSE-BOT", use_container_width=True)
    tabs = st.tabs(["Login", "Signup"])
    with tabs[0]:
        login()
    with tabs[1]:
        signup()
else:
    main_ui()
########################################################################################################################
