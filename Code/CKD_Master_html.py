import os
import sys
import logging
import warnings
import platform
import pandas as pd  # type: ignore

# Setup logging
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

# Log EMIS directory contents
try:
    emis_contents = os.listdir(emis_path)
    logging.info(f"EMIS_Files contents: {emis_contents}")
except Exception as e:
    logging.error(f"Failed to list EMIS_Files contents: {e}")
    sys.exit(1)

warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)

# Import the main CKD processing logic
from CKD_core import *

# Detect the operating system and import the appropriate wkhtmltopdf setup file
if platform.system() == "Windows":
    from CKD_windows_core import *  # Windows-specific setup
elif platform.system() == "Darwin":  # macOS
    from CKD_mac_core import *  # macOS-specific setup
else:
    raise EnvironmentError("Unsupported operating system. This script only supports Windows and macOS.")

# Import the HTML module
from CKD_html_files import *