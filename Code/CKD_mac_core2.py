import os
import sys
import subprocess
import requests
import shutil
import tempfile
import platform
import pdfkit  # type: ignore
import logging

# Setup logging to match CKD pipeline
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Define configuration
WKHTMLTOPDF_PATH = "/usr/local/bin/wkhtmltopdf"  # Default install path
DOWNLOAD_URL = "https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox-0.12.6-1.macos-cocoa.pkg"

def install_wkhtmltopdf_macos(download_url=DOWNLOAD_URL, wkhtmltopdf_path=WKHTMLTOPDF_PATH):
    """Install wkhtmltopdf on macOS via direct .pkg download."""
    if not os.path.exists(wkhtmltopdf_path):
        logging.info("wkhtmltopdf not found at %s, installing...", wkhtmltopdf_path)
        
        # Use a temporary file for the .pkg
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pkg") as tmp:
            installer_path = tmp.name
        
        # Download the .pkg file
        logging.info("Downloading wkhtmltopdf from %s", download_url)
        try:
            response = requests.get(download_url, stream=True, timeout=30)
            response.raise_for_status()
            with open(installer_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            logging.info("Download completed. Size: %d bytes", os.path.getsize(installer_path))
        except Exception as e:
            logging.error("Download failed: %s", e)
            raise

        # Install the .pkg file
        try:
            logging.info("Installing wkhtmltopdf via pkg installer...")
            subprocess.run(["sudo", "installer", "-pkg", installer_path, "-target", "/"], check=True)
            logging.info("Installation completed.")
        except subprocess.CalledProcessError as e:
            logging.error("Installation failed: %s", e)
            raise
        finally:
            if os.path.exists(installer_path):
                os.remove(installer_path)
                logging.info("Temporary installer file removed.")

    # Verify installation
    try:
        result = subprocess.run(
            [wkhtmltopdf_path, "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        logging.info("wkhtmltopdf verified: %s", result.stdout.strip())
    except subprocess.CalledProcessError as e:
        logging.error("wkhtmltopdf installed but not working: %s", e)
        raise

    return wkhtmltopdf_path

def setup_wkhtmltopdf():
    """Setup wkhtmltopdf and return pdfkit configuration."""
    if platform.system() != "Darwin":
        logging.error("This script is intended for macOS systems only.")
        sys.exit(1)

    # Install wkhtmltopdf if not present
    path_to_wkhtmltopdf = install_wkhtmltopdf_macos()
    
    # Configure pdfkit
    try:
        config = pdfkit.configuration(wkhtmltopdf=path_to_wkhtmltopdf)
        logging.info("pdfkit configured successfully.")
        return config
    except Exception as e:
        logging.error(f"Error configuring pdfkit: {e}")
        sys.exit(1)

# Variables for import compatibility with CKD Master PDF
path_to_wkhtmltopdf = WKHTMLTOPDF_PATH
pdfkit_config = setup_wkhtmltopdf()

if __name__ == "__main__":
    logging.info("wkhtmltopdf setup completed for standalone execution.")