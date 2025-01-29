import pandas as pd  # type: ignore
import os
import shutil
import subprocess
import warnings
import sys
import platform
import pdfkit  # type: ignore
warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)

def is_homebrew_installed():
    """Check if Homebrew is installed on the system."""
    try:
        subprocess.run(["brew", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("Homebrew is already installed.")
        return True
    except Exception as e:
        print("Homebrew is not installed.")
        return False

def install_homebrew():
    """Install Homebrew on macOS."""
    try:
        print("Installing Homebrew...")
        # Run the Homebrew installation script
        subprocess.run(
            ['/bin/bash', '-c', "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"],
            check=True
        )
        print("Homebrew installation completed.")
    except subprocess.CalledProcessError as e:
        print("Failed to install Homebrew.")
        sys.exit(1)

def is_wkhtmltopdf_installed():
    """Check if wkhtmltopdf is installed on the system."""
    try:
        subprocess.run(["wkhtmltopdf", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("wkhtmltopdf is already installed.")
        return True
    except Exception as e:
        print("wkhtmltopdf is not installed.")
        return False

def install_wkhtmltopdf():
    """Install wkhtmltopdf using multiple methods."""
    try:
        print("Attempting to install wkhtmltopdf via Homebrew...")
        # First try the main formula
        subprocess.run(["brew", "install", "wkhtmltopdf"], check=True)
    except subprocess.CalledProcessError:
        try:
            print("Main formula failed, trying alternative cask...")
            # Try installing from an alternative source
            subprocess.run(["brew", "install", "--cask", "wkhtmltopdf"], check=True)
        except subprocess.CalledProcessError:
            try:
                print("Cask failed, trying direct download...")
                # Direct download as last resort
                download_url = "https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox-0.12.6-1.macos-cocoa.pkg"
                download_path = "/tmp/wkhtmltopdf.pkg"
                
                # Download the package
                subprocess.run(["curl", "-L", download_url, "-o", download_path], check=True)
                
                # Install the package
                subprocess.run(["sudo", "installer", "-pkg", download_path, "-target", "/"], check=True)
                
                # Clean up
                os.remove(download_path)
                
            except subprocess.CalledProcessError as e:
                print(f"All installation methods failed: {str(e)}")
                print("Please install wkhtmltopdf manually from: https://wkhtmltopdf.org/downloads.html")
                sys.exit(1)

def verify_wkhtmltopdf():
    """Verify wkhtmltopdf installation and return path."""
    possible_paths = [
        '/usr/local/bin/wkhtmltopdf',
        '/usr/bin/wkhtmltopdf',
        '/opt/homebrew/bin/wkhtmltopdf',
        '/Applications/wkhtmltopdf.app/Contents/MacOS/wkhtmltopdf'
    ]
    
    # First check PATH
    path_to_wkhtmltopdf = shutil.which("wkhtmltopdf")
    if path_to_wkhtmltopdf:
        return path_to_wkhtmltopdf
    
    # Then check common installation locations
    for path in possible_paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
            
    return None

# Ensure wkhtmltopdf is installed
if not is_wkhtmltopdf_installed():
    print("wkhtmltopdf is required to generate PDFs.")
    print("Attempting to install wkhtmltopdf automatically...")
    install_wkhtmltopdf()
else:
    print("wkhtmltopdf is already installed.")

# Dynamically find the path to wkhtmltopdf
path_to_wkhtmltopdf = shutil.which("wkhtmltopdf")
if path_to_wkhtmltopdf is None:
    # Try common installation paths
    possible_paths = [
        '/usr/local/bin/wkhtmltopdf',
        '/usr/bin/wkhtmltopdf',
        '/opt/homebrew/bin/wkhtmltopdf'  # For Apple Silicon Macs
    ]
    for path in possible_paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            path_to_wkhtmltopdf = path
            break

if path_to_wkhtmltopdf is None:
    print("wkhtmltopdf not found in PATH or common directories.")
    sys.exit(1)

# Check if the script is running on macOS
if platform.system() != 'Darwin':
    print("This script is intended for macOS systems.")
    sys.exit(1)

# Ensure Homebrew is installed
if not is_homebrew_installed():
    print("Attempting to install wkhtmltopdf automatically...")
    install_wkhtmltopdf()

# Dynamically find the path to wkhtmltopdf
path_to_wkhtmltopdf = shutil.which("wkhtmltopdf")
if path_to_wkhtmltopdf is None:
    print("wkhtmltopdf not found in PATH.")
    sys.exit(1)

# Set up pdfkit configuration with the path to wkhtmltopdf
config = pdfkit.configuration(wkhtmltopdf=path_to_wkhtmltopdf)
print("pdfkit configured successfully.")