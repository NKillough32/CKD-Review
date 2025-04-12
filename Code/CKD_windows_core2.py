import os
import sys
import subprocess
import requests
import logging
import tempfile
import platform
import argparse
import ctypes
from tqdm import tqdm
import pdfkit

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler("windows_core_generation.log")]
)

# Configuration class for centralizing settings
class Config:
    WINDOWS = {
        "WKHTMLTOPDF_PATH": "C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe",
        "DOWNLOAD_URL": "https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox-0.12.6-1.msvc2015-win64.exe"
    }
    MACOS = {
        "WKHTMLTOPDF_PATH": "/usr/local/bin/wkhtmltopdf",
        "INSTALL_CMD": ["brew", "install", "wkhtmltopdf"]
    }

# Parse command-line arguments
def parse_args():
    parser = argparse.ArgumentParser(description="Setup wkhtmltopdf and configure pdfkit.")
    parser.add_argument("--wkhtmltopdf-path", help="Path to wkhtmltopdf executable")
    parser.add_argument("--installer-url", help="URL to download wkhtmltopdf installer (Windows only)")
    return parser.parse_args()

# Check if running with admin privileges (Windows only)
def is_admin():
    if platform.system() == "Windows":
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except Exception:
            return False
    return True  # Non-Windows systems don't require this check here

# Download wkhtmltopdf installer with progress bar (Windows only)
def download_wkhtmltopdf(installer_path, url):
    logging.info("Downloading wkhtmltopdf from %s", url)
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        with tqdm(total=total_size, unit='iB', unit_scale=True) as pbar:
            with open(installer_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))
        logging.info("Download completed. Size: %d bytes", total_size)
    except (requests.ConnectionError, requests.Timeout, requests.RequestException) as e:
        logging.error("Download failed: %s", e)
        raise

# Install and verify wkhtmltopdf
def setup_wkhtmltopdf(config, installer_path=None):
    wkhtmltopdf_path = config["WKHTMLTOPDF_PATH"]
    os_name = platform.system()

    if not os.path.exists(wkhtmltopdf_path):
        logging.info("wkhtmltopdf not found at %s, installing...", wkhtmltopdf_path)
        if os_name == "Windows":
            if not installer_path:
                raise ValueError("Installer path required for Windows installation")
            if not os.path.exists(installer_path):
                download_wkhtmltopdf(installer_path, config["DOWNLOAD_URL"])
            try:
                logging.info("Running silent installation...")
                subprocess.run([installer_path, "/S"], check=True)
                logging.info("Silent installation completed.")
            except subprocess.CalledProcessError as e:
                logging.error("Silent installation failed: %s", e)
                raise
        elif os_name == "Darwin":
            try:
                logging.info("Installing wkhtmltopdf via Homebrew...")
                subprocess.run(config["INSTALL_CMD"], check=True)
                logging.info("Installation completed.")
            except subprocess.CalledProcessError as e:
                logging.error("Homebrew installation failed: %s", e)
                raise
        else:
            raise EnvironmentError(f"Unsupported OS: {os_name}")

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

# Cleanup temporary files
def cleanup(installer_path):
    if installer_path and os.path.exists(installer_path):
        try:
            os.remove(installer_path)
            logging.info("Cleanup: Installer removed.")
        except OSError as e:
            logging.warning("Failed to remove installer: %s", e)

# Main execution
def main():
    args = parse_args()
    os_name = platform.system()

    # Select config based on OS
    if os_name == "Windows":
        config = Config.WINDOWS.copy()
    elif os_name == "Darwin":
        config = Config.MACOS.copy()
    else:
        logging.error("Unsupported operating system: %s", os_name)
        sys.exit(1)

    # Override config with command-line args if provided
    if args.wkhtmltopdf_path:
        config["WKHTMLTOPDF_PATH"] = args.wkhtmltopdf_path
    if args.installer_url and os_name == "Windows":
        config["DOWNLOAD_URL"] = args.installer_url

    installer_path = None
    try:
        if not is_admin():
            logging.info("Admin privileges required, requesting elevation...")
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
            return

        # Create a temporary file for the installer (Windows only)
        if os_name == "Windows":
            with tempfile.NamedTemporaryFile(delete=False, suffix=".exe") as tmp:
                installer_path = tmp.name

        # Setup wkhtmltopdf
        setup_wkhtmltopdf(config, installer_path)

        # Configure pdfkit
        pdfkit_config = pdfkit.configuration(wkhtmltopdf=config["WKHTMLTOPDF_PATH"])
        logging.info("pdfkit configured successfully.")
        
    except Exception as e:
        logging.error("Script failed: %s", e)
        cleanup(installer_path)
        sys.exit(1)
    finally:
        cleanup(installer_path)

if __name__ == "__main__":
    main()