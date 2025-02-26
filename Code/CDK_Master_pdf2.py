import pandas as pd  # type: ignore
import os
import warnings
import platform
import ctypes
import sys
import tempfile
import pdfkit  # type: ignore
import logging

# Setup logging to match CKD_windows_core2
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)

# Check admin status at the beginning
def is_admin():
    if platform.system() == "Windows":
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except Exception:
            return False
    return True

# Request elevation if needed and exit
if not is_admin():
    logging.info("Admin privileges required. Requesting elevation...")
    if platform.system() == "Windows":
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, __file__, None, 1)
    sys.exit()

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

# Detect the operating system and import the appropriate wkhtmltopdf setup file
installer_path = None
try:
    if platform.system() == "Windows":
        from CKD_windows_core2 import *  # Import setup_wkhtmltopdf from CKD_windows_core2

        # Create a temporary file for the installer
        with tempfile.NamedTemporaryFile(delete=False, suffix=".exe") as tmp:
            installer_path = tmp.name

        # Setup wkhtmltopdf with config and installer_path
        config = Config.WINDOWS
        logging.info(f"Setting up wkhtmltopdf with config={config}, installer_path={installer_path}")
        
        # Ensure installer_path is empty or valid before proceeding
        if os.path.exists(installer_path) and os.path.getsize(installer_path) == 0:
            logging.info(f"Removing empty installer file at {installer_path}")
            os.remove(installer_path)

        setup_wkhtmltopdf(config, installer_path)  # Call matches CKD_windows_core2 definition
        pdfkit_config = pdfkit.configuration(wkhtmltopdf=config["WKHTMLTOPDF_PATH"])
        logging.info("wkhtmltopdf and pdfkit configured successfully.")

    elif platform.system() == "Darwin":  # macOS
        from CKD_mac_core import *  # macOS-specific setup
        config = Config.MACOS
        # Assuming CKD_mac_core defines path_to_wkhtmltopdf or a setup function
        pdfkit_config = pdfkit.configuration(wkhtmltopdf=path_to_wkhtmltopdf)
        logging.info("wkhtmltopdf and pdfkit configured successfully.")
    else:
        raise EnvironmentError("Unsupported operating system. This script only supports Windows and macOS.")

    # Import the PDF module
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