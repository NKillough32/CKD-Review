import pandas as pd  # type: ignore
import os
import warnings
import platform 
warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)

# Get the current working directory
current_dir = os.getcwd()

# Import the main CKD processing logic
from CKD_core1 import * #as process_ckd_data
from CKD_pdf_files import *# as generate_patient_pdf # Import PDF generation
from CKD_html_files import * # as generate_patient_html# Import HTML report generation

# Detect the operating system and import the appropriate wkhtmltopdf setup file
if platform.system() == "Windows":
    from CKD_windows_core import *  # Windows-specific setup
elif platform.system() == "Darwin":  # macOS
    from CKD_mac_core import *  # macOS-specific setup
else:
    raise EnvironmentError("Unsupported operating system. This script only supports Windows and macOS.")

def main():
    print("\nStarting CKD Auto Processing...")

    # Process CKD data
    processed_data = process_ckd_data()

    # Generate reports
    date_folder_html = generate_patient_html(processed_data)
    date_folder_pdf = generate_patient_pdf(processed_data)

    print("\nCKD Analysis and Reporting Completed.")
    print(f"All reports saved in: {date_folder_pdf} and {date_folder_html}")

if __name__ == "__main__":
    main()