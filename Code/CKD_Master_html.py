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

# Set up paths before any imports that need them
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
    # Use current working directory for dynamic files
    working_base_path = os.getcwd()
    emis_path = os.path.join(working_base_path, "EMIS_Files")
    dependencies_path = os.path.join(working_base_path, "Dependencies")
else:
    base_path = os.getcwd()
    working_base_path = base_path
    emis_path = os.path.join(base_path, "EMIS_Files")
    dependencies_path = os.path.join(base_path, "Dependencies")

# Set environment variables for other modules
os.environ['EMIS_FILES_PATH'] = emis_path
os.environ['DEPENDENCIES_PATH'] = dependencies_path

# Verify directories exist
for path, name in [(emis_path, "EMIS_Files"), (dependencies_path, "Dependencies")]:
    if not os.path.exists(path):
        logging.error(f"{name} directory not found at: {path}")
        logging.error(f"Please ensure {name} directory is present alongside the executable")
        sys.exit(1)

# Log EMIS directory contents
try:
    emis_contents = os.listdir(emis_path)
    logging.info(f"EMIS_Files contents: {emis_contents}")
except Exception as e:
    logging.error(f"Failed to list EMIS_Files contents: {e}")
    sys.exit(1)

# Now import the main CKD processing logic
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