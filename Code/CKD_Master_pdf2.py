import pandas as pd  # type: ignore
import os
import warnings
import platform
import ctypes
import sys
import tempfile
import pdfkit  # type: ignore
import logging
import webbrowser  # For opening the installer file
import urllib.request  # For downloading the installer
import time  # For adding a small delay

# Setup logging to match CKD_windows_core2
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
# Set up EMIS_FILES_PATH before any imports that need it
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
    # Use the current working directory for EMIS files
    emis_path = os.path.join(os.getcwd(), "EMIS_Files")
else:
    base_path = os.getcwd()
    emis_path = os.path.join(base_path, "EMIS_Files")

# Set environment variable for other modules
os.environ['EMIS_FILES_PATH'] = emis_path

# Verify EMIS directory exists
if not os.path.exists(emis_path):
    logging.error(f"EMIS_Files directory not found at: {emis_path}")
    logging.error("Please ensure EMIS_Files directory is present alongside the executable")
    sys.exit(1)

warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)

# Check admin status at the beginning (no elevation request anymore)
def is_admin():
    if platform.system() == "Windows":
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except Exception:
            return False
    return True

# Log admin status but don't attempt elevation—proceed without it if not present
admin_status = is_admin()
logging.info(f"Running with admin privileges: {admin_status}. Proceeding to test functionality...")

# Get the current working directory
current_dir = os.getcwd()

# Import the main CKD processing logic
from CKD_core import *

# Define configuration for wkhtmltopdf setup (matching CKD_windows_core2)
class Config:
    WINDOWS = {
        "WKHTMLTOPDF_PATH": "C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe",
        "DOWNLOAD_URL": "https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox-0.12.6-1.msvc2015-win64.exe"
    }
    MACOS = {
        "WKHTMLTOPDF_PATH": "/usr/local/bin/wkhtmltopdf",
        "INSTALL_CMD": ["brew", "install", "wkhtmltopdf"]
    }

# Function to check if wkhtmltopdf is installed
def check_wkhtmltopdf_installed(path):
    return os.path.exists(path)

# Detect the operating system and attempt wkhtmltopdf setup
installer_path = None
pdfkit_config = None
try:
    if platform.system() == "Windows":
        from CKD_windows_core2 import *  # Import setup_wkhtmltopdf from CKD_windows_core2

        # Create a temporary file for the installer
        with tempfile.NamedTemporaryFile(delete=False, suffix=".exe") as tmp:
            installer_path = tmp.name

        # Setup wkhtmltopdf with config and installer_path
        config = Config.WINDOWS
        logging.info(f"Attempting to set up wkhtmltopdf with config={config}, installer_path={installer_path}")
        
        # Ensure installer_path is empty or valid before proceeding
        if os.path.exists(installer_path) and os.path.getsize(installer_path) == 0:
            logging.info(f"Removing empty installer file at {installer_path}")
            os.remove(installer_path)

        # Try to configure pdfkit without installing if possible
        try:
            # Check if wkhtmltopdf is already installed in a user-accessible location
            potential_paths = [
                config["WKHTMLTOPDF_PATH"],  # Default system path
                os.path.join(os.environ["LOCALAPPDATA"], "wkhtmltopdf", "bin", "wkhtmltopdf.exe")  # User path
            ]
            wkhtmltopdf_path = None
            for path in potential_paths:
                if os.path.exists(path):
                    wkhtmltopdf_path = path
                    break

            if wkhtmltopdf_path:
                pdfkit_config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
                logging.info(f"wkhtmltopdf found at {wkhtmltopdf_path}. Configured successfully without elevation.")
            else:
                if admin_status:
                    # Attempt silent installation only if admin rights are present
                    logging.info("Admin rights detected. Attempting silent installation of wkhtmltopdf...")
                    setup_wkhtmltopdf(config, installer_path)  # Call matches CKD_windows_core2 definition
                    pdfkit_config = pdfkit.configuration(wkhtmltopdf=config["WKHTMLTOPDF_PATH"])
                    logging.info("wkhtmltopdf installed and configured successfully.")
                else:
                    # Fall back to manual installation if no admin rights (no elevation attempt)
                    logging.warning("No admin privileges detected. Downloading installer for manual installation...")
                    
                    # Download the installer
                    try:
                        urllib.request.urlretrieve(config["DOWNLOAD_URL"], installer_path)
                        logging.info(f"Installer downloaded to {installer_path}. Please run it to install wkhtmltopdf.")
                        
                        # Open the installer for the user to run manually
                        os.startfile(installer_path)  # This opens the .exe in Windows
                        logging.info("Installer opened. Please install wkhtmltopdf with admin privileges.")

                        # Wait a moment for the user to potentially install
                        time.sleep(5)  # Give the user a few seconds to start the installation

                        # Check if installation succeeded, allow up to 3 attempts
                        attempt = 0
                        max_attempts = 3
                        while attempt < max_attempts:
                            user_input = input(f"Has wkhtmltopdf been installed successfully? (yes/no) [Attempt {attempt + 1}/{max_attempts}]: ").lower().strip()
                            if user_input == 'yes':
                                if check_wkhtmltopdf_installed(config["WKHTMLTOPDF_PATH"]):
                                    pdfkit_config = pdfkit.configuration(wkhtmltopdf=config["WKHTMLTOPDF_PATH"])
                                    logging.info("wkhtmltopdf confirmed installed and configured successfully.")
                                    break
                                else:
                                    logging.warning("wkhtmltopdf not found at the expected path. Please verify installation.")
                                    attempt += 1
                                    if attempt < max_attempts:
                                        print(f"Attempt {attempt + 1}/{max_attempts}. Please ensure wkhtmltopdf is installed correctly.")
                                    continue
                            elif user_input == 'no':
                                attempt += 1
                                if attempt < max_attempts:
                                    print(f"Attempt {attempt + 1}/{max_attempts}. Please install wkhtmltopdf and try again.")
                                continue
                            else:
                                print("Please enter 'yes' or 'no'.")
                                continue

                        if attempt >= max_attempts:
                            logging.error("Failed to confirm wkhtmltopdf installation after 3 attempts. Exiting script.")
                            sys.exit(1)

                        # If we reach here, installation is confirmed—proceed
                        logging.info("Continuing with script execution after successful installation confirmation.")

                    except Exception as e:
                        logging.error(f"Failed to download or open installer: {e}")
                        pdfkit_config = None  # Proceed without PDF functionality
                        logging.warning("Continuing without PDF functionality. Please install wkhtmltopdf and restart the script.")

        except PermissionError as pe:
            if not admin_status:
                logging.warning(f"Permission denied during wkhtmltopdf setup: {pe}. Skipping installation (requires admin privileges).")
                pdfkit_config = None  # Proceed without PDF functionality if not critical
            else:
                raise  # Re-raise if admin but still failing

    elif platform.system() == "Darwin":  # macOS
        from CKD_mac_core2 import *  # macOS-specific setup
        config = Config.MACOS
        # Assuming CKD_mac_core defines path_to_wkhtmltopdf or a setup function
        pdfkit_config = pdfkit.configuration(wkhtmltopdf=path_to_wkhtmltopdf)
        logging.info("wkhtmltopdf and pdfkit configured successfully.")

    else:
        raise EnvironmentError("Unsupported operating system. This script only supports Windows and macOS.")

    # Import the PDF module if setup succeeds
    from CKD_pdf_files import *

except Exception as e:
    logging.error(f"Failed to setup wkhtmltopdf: {e}")
    sys.exit(1)
finally:
    # Cleanup temporary installer file if it exists
    if installer_path and os.path.exists(installer_path):
        try:
            os.remove(installer_path)
            logging.info("Temporary installer file removed.")
        except OSError as e:
            logging.warning(f"Failed to remove temporary installer file: {e}")

# If we reach here, setup worked—proceed with your script’s logic
logging.info("Setup complete, continuing with main script execution...")