import pandas as pd  # type: ignore
import os
import subprocess
import requests  # type: ignore
import warnings
import pdfkit  # type: ignore
warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)

# Define path to wkhtmltopdf executable and installer
path_to_wkhtmltopdf = "C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe"  # Adjust for your system
installer_path = "wkhtmltox-installer.exe"
url = "https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox-0.12.6-1.msvc2015-win64.exe"

def download_wkhtmltopdf(installer_path, url):
    """Download the wkhtmltopdf installer."""
    print("Downloading wkhtmltopdf installer...")
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(installer_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=1024):
                file.write(chunk)
        print("Download completed successfully.")
    except requests.RequestException as e:
        print(f"Error downloading the installer: {e}")
        exit(1)

# Check if wkhtmltopdf is installed; if not, download and install
if not os.path.exists(path_to_wkhtmltopdf):
    print("wkhtmltopdf executable not found.")
    
    # Download the installer if it doesn't exist
    if not os.path.exists(installer_path):
        download_wkhtmltopdf(installer_path, url)

try:
    print("Attempting silent installation...")
    subprocess.run(f'"{installer_path}" /S', check=True, shell=True)
    print("Silent installation completed successfully.")
except subprocess.CalledProcessError as e:
    print(f"Silent installation failed with error code {e.returncode}.")
    print("\nThe wkhtmltopdf installer has been downloaded.")
    print("Attempting to open the installer manually...")

    try:
        # Open the installer interactively
        subprocess.run(f'"{installer_path}"', check=True, shell=True)
        print("Installer opened successfully. Please complete the installation.")
    except Exception as manual_install_error:
        print(f"Failed to open the installer: {manual_install_error}")
        print(f"Please locate and run the installer manually: {os.path.abspath(installer_path)}")
        input("After completing the installation, press Enter to continue...")

    # Re-check if wkhtmltopdf is installed
    if not os.path.exists(path_to_wkhtmltopdf):
        print("Installation not detected. Please ensure wkhtmltopdf is installed correctly.")
        exit(1)

# Remove the installer after successful installation
if os.path.exists(installer_path):
    os.remove(installer_path)
    print("Installer removed successfully.")

# Configure pdfkit to use wkhtmltopdf
try:
    config = pdfkit.configuration(wkhtmltopdf=path_to_wkhtmltopdf)
    print("pdfkit configured successfully.")
except Exception as e:
    print(f"Error configuring pdfkit: {e}")
    exit(1)
