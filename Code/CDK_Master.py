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

# Ask the user for their preferred output format
output_format = input("Enter the preferred output format (pdf(1)/html(2)): ").strip().lower()

# Import the appropriate module based on user input
if output_format == "pdf" or output_format == "1":
    from CKD_pdf_files import *  
elif output_format == "html" or output_format == "2":
    from CKD_html_files import *  
else:
    attempts = 0
    while attempts < 3:
        output_format = input("Invalid format. Please enter 'pdf' or 'html': ").strip().lower()
        if output_format in ["pdf", "html"]:
            break
        attempts += 1
    else:
        raise ValueError("Invalid output format after 3 attempts. Please enter 'pdf' or 'html'.")