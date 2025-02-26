import pandas as pd  # type: ignore
import os
import warnings
import platform
import ctypes
import sys
import pdfkit  # type: ignore

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
    print("Admin privileges required. Requesting elevation...")
    if platform.system() == "Windows":
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, __file__, None, 1)
    sys.exit()

# Get the current working directory
current_dir = os.getcwd()

# Import the main CKD processing logic
from CKD_core import *

# Define configuration for wkhtmltopdf setup
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
if platform.system() == "Windows":
    from CKD_windows_core2 import *  # Updated to CKD_windows_core2

    # Setup wkhtmltopdf with config
    try:
        config = Config.WINDOWS  # Provide the config dictionary
        setup_wkhtmltopdf(config)  # Call the function with the required argument
        pdfkit_config = pdfkit.configuration(wkhtmltopdf=config["WKHTMLTOPDF_PATH"])
        print("wkhtmltopdf and pdfkit configured successfully.")
    except Exception as e:
        print(f"Failed to setup wkhtmltopdf: {e}")
        sys.exit(1)

elif platform.system() == "Darwin":  # macOS
    from CKD_mac_core import *  # macOS-specific setup
    # Assuming CKD_mac_core defines its own setup logic or variables
    try:
        config = Config.MACOS
        # If CKD_mac_core has a similar setup function, call it here
        # Otherwise, assume it defines path_to_wkhtmltopdf
        pdfkit_config = pdfkit.configuration(wkhtmltopdf=path_to_wkhtmltopdf)
        print("wkhtmltopdf and pdfkit configured successfully.")
    except Exception as e:
        print(f"Failed to setup wkhtmltopdf on macOS: {e}")
        sys.exit(1)
else:
    raise EnvironmentError("Unsupported operating system. This script only supports Windows and macOS.")

# Import the PDF module
from CKD_pdf_files import *