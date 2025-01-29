import pandas as pd  # type: ignore
import os
import warnings
import platform 
warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)

# Get the current working directory
current_dir = os.getcwd()

# Import the main CKD processing logic
from CKD_core1 import * 

# Detect the operating system and import the appropriate wkhtmltopdf setup file
if platform.system() == "Windows":
    from CKD_windows_core import *  # Windows-specific setup
elif platform.system() == "Darwin":  # macOS
    from CKD_mac_core import *  # macOS-specific setup
else:
    raise EnvironmentError("Unsupported operating system. This script only supports Windows and macOS.")

# Ask the user for their preferred output format
output_format = input("Enter the preferred output format (pdf/html): ").strip().lower()

# Import the appropriate module based on user input
if output_format == "pdf":
    from CKD_pdf_files import *  
elif output_format == "html":
    from CKD_html_files import *  
else:
    raise ValueError("Invalid output format. Please enter 'pdf' or 'html'.")