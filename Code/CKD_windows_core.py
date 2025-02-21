import pandas as pd  # type: ignore
import os
import subprocess
import requests  # type: ignore
import warnings
import pdfkit  # type: ignore
import tempfile

warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)

# Define path to wkhtmltopdf executable and installer
path_to_wkhtmltopdf = "C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe"  # Adjust for your system
installer_path = os.path.join(tempfile.gettempdir(), "wkhtmltox-installer.exe")
url = "https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox-0.12.6-1.msvc2015-win64.exe"

def download_wkhtmltopdf(installer_path, url):
    """Download the wkhtmltopdf installer."""
    print("Downloading wkhtmltopdf installer...")
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        with open(installer_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
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
        subprocess.run([installer_path, "/S"], check=True)
        print("Silent installation completed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Silent installation failed with error code {e.returncode}.")
        print("\nThe wkhtmltopdf installer has been downloaded.")
        print("Attempting to open the installer manually...")

        try:
            # Open the installer interactively
            subprocess.run([installer_path], check=True)
            print("Installer opened successfully. Please complete the installation.")
        except Exception as manual_install_error:
            print(f"Failed to open the installer: {manual_install_error}")
            print(f"Please locate and run the installer manually: {installer_path}")
            input("After completing the installation, press Enter to continue...")

        # Re-check if wkhtmltopdf is installed
        if not os.path.exists(path_to_wkhtmltopdf):
            print("Installation not detected. Please ensure wkhtmltopdf is installed correctly.")
            exit(1)

# Verify installation by running wkhtmltopdf --version
try:
    subprocess.run([path_to_wkhtmltopdf, "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print("wkhtmltopdf is installed and working correctly.")
except subprocess.CalledProcessError:
    print("wkhtmltopdf installation detected but not working. Please check the installation manually.")
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
