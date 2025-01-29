import pandas as pd  # type: ignore
import os
import warnings
import platform 
warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)

# Get the current working directory
current_dir = os.getcwd()

# Import the main CKD processing logic
from CKD_core import * 

# Detect the operating system and import the appropriate wkhtmltopdf setup file
if platform.system() == "Windows":
    from CKD_windows_core import *  # Windows-specific setup
elif platform.system() == "Darwin":  # macOS
    from CKD_mac_core import *  # macOS-specific setup
else:
    raise EnvironmentError("Unsupported operating system. This script only supports Windows and macOS.")

# Import the PDF module
from CKD_pdf_files import *  