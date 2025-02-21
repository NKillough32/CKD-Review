import pandas as pd  # type: ignore
import os
import warnings
import platform
import ctypes
import sys
import subprocess
import pdfkit  # type: ignore
warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)

# Get the current working directory
current_dir = os.getcwd()

# Import the main CKD processing logic
from CKD_core import *

# check admin status
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

# Detect the operating system and import the appropriate wkhtmltopdf setup file
if platform.system() == "Windows":
    from CKD_windows_core import *  # Windows-specific setup

    if not is_admin():
        # Re-run the script with elevation
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, __file__, None, 1)
        sys.exit()

    # Ensure wkhtmltopdf is installed and configured
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

elif platform.system() == "Darwin":  # macOS
    from CKD_mac_core import *  # macOS-specific setup
else:
    raise EnvironmentError("Unsupported operating system. This script only supports Windows and macOS.")

# Import the PDF module
from CKD_pdf_files import *
