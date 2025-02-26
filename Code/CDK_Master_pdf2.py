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

# Detect the operating system and import the appropriate wkhtmltopdf setup file
if platform.system() == "Windows":
    from CKD_windows_core2 import *  # Updated to CKD_windows_core2

    # Setup wkhtmltopdf (assumes CKD_windows_core2 provides this function)
    try:
        config = setup_wkhtmltopdf()  # Replace with actual function name
        print("wkhtmltopdf and pdfkit configured successfully.")
    except Exception as e:
        print(f"Failed to setup wkhtmltopdf: {e}")
        sys.exit(1)

elif platform.system() == "Darwin":  # macOS
    from CKD_mac_core import *  # macOS-specific setup
else:
    raise EnvironmentError("Unsupported operating system. This script only supports Windows and macOS.")

# Import the PDF module
from CKD_pdf_files import *