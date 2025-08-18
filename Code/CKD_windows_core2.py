import os
import sys
import subprocess
import requests
import logging
import tempfile
import platform
import argparse
import ctypes
import shutil
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

def parse_args():
    parser = argparse.ArgumentParser(description="Setup wkhtmltopdf and configure pdfkit.")
    parser.add_argument("--wkhtmltopdf-path", help="Path to wkhtmltopdf executable")
    parser.add_argument("--installer-url", help="URL to download wkhtmltopdf installer (Windows only)")
    return parser.parse_args()

def find_wkhtmltopdf(config_path: str | None = None) -> str | None:
    """
    Return a usable wkhtmltopdf absolute path if found, else None.
    Order: explicit config path → env overrides → PATH → common install locations.
    """
    # 1) Explicit config path
    if config_path and os.path.isfile(config_path):
        return config_path

    # 2) Env overrides
    for env_key in ("WKHTMLTOPDF_PATH", "WKHTMLTOPDF_BINARY"):
        p = os.environ.get(env_key)
        if p and os.path.isfile(p):
            return p

    # 3) PATH
    p = shutil.which("wkhtmltopdf")
    if p:
        return p

    # 4) Common locations by OS/arch
    sysname = platform.system()

    candidates: list[str] = []
    if sysname == "Windows":
        candidates += [
            r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
            r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
            r"C:\ProgramData\chocolatey\bin\wkhtmltopdf.exe",
        ]
    elif sysname == "Darwin":
        # Apple Silicon first, then Intel
        candidates += [
            "/opt/homebrew/bin/wkhtmltopdf",
            "/usr/local/bin/wkhtmltopdf",
        ]

    for c in candidates:
        if os.path.isfile(c):
            return c
    return None

# Check if running with admin privileges (Windows only)
def is_admin():
    if platform.system() == "Windows":
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except Exception:
            return False
    return True  # Non-Windows systems don't require this check here

# Download wkhtmltopdf installer with progress bar (Windows only)
def download_wkhtmltopdf(installer_path, url, timeout=120):
    logging.info("Downloading wkhtmltopdf from %s", url)
    with requests.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        with tqdm(total=total, unit='iB', unit_scale=True) as pbar, open(installer_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024*64):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))
    size = os.path.getsize(installer_path)
    if total and size != total:
        logging.warning("Downloaded size (%d) != content-length (%d).", size, total)
    logging.info("Download completed (%d bytes).", size)

# Install and verify wkhtmltopdf
def setup_wkhtmltopdf(config, installer_path=None):
    os_name = platform.system()

    # Already installed?
    binary = find_wkhtmltopdf(config.get("WKHTMLTOPDF_PATH"))
    if binary:
        logging.info("wkhtmltopdf found at %s", binary)
    else:
        logging.info("wkhtmltopdf not found, installing...")

        if os_name == "Windows":
            if not installer_path:
                raise ValueError("Installer path required for Windows installation")
            if not os.path.exists(installer_path):
                download_wkhtmltopdf(installer_path, config["DOWNLOAD_URL"], timeout=120)
            logging.info("Running silent installation...")
            subprocess.run([installer_path, "/S"], check=True)
        elif os_name == "Darwin":
            # Ensure Homebrew is available
            if not shutil.which("brew"):
                raise EnvironmentError("Homebrew not found. Install Homebrew first: https://brew.sh/")
            logging.info("Installing wkhtmltopdf via Homebrew...")
            subprocess.run(config["INSTALL_CMD"], check=True)
        else:
            raise EnvironmentError(f"Unsupported OS: {os_name}")

        # Re-discover after install
        binary = find_wkhtmltopdf(config.get("WKHTMLTOPDF_PATH"))

    if not binary:
        raise FileNotFoundError("wkhtmltopdf not detected after installation.")

    # Verify version
    result = subprocess.run([binary, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"wkhtmltopdf present but not working: {result.stderr.strip()}")
    logging.info("wkhtmltopdf verified: %s", result.stdout.strip())

    # Configure pdfkit and do a render smoke test
    cfg = pdfkit.configuration(wkhtmltopdf=binary)
    smoke_test_pdf = os.path.join(tempfile.gettempdir(), "wkhtmltopdf_smoke.pdf")
    try:
        pdfkit.from_string("<h1>wkhtmltopdf OK</h1>", smoke_test_pdf, configuration=cfg)
        if os.path.exists(smoke_test_pdf) and os.path.getsize(smoke_test_pdf) > 0:
            logging.info("pdfkit configured and render test succeeded.")
            os.remove(smoke_test_pdf)  # cleanup
        else:
            logging.warning("Render test created empty or missing file.")
    except Exception as e:
        logging.error("Render test failed: %s", e)
        raise

    # Update config path to the discovered binary for callers
    config["WKHTMLTOPDF_PATH"] = binary
    
    return cfg

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
        if not is_admin() and platform.system() == "Windows":
            logging.info("Admin privileges required, requesting elevation...")
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
            sys.exit(0)  # ensure this instance exits

        # Create a temporary file for the installer (Windows only)
        if os_name == "Windows":
            with tempfile.NamedTemporaryFile(delete=False, suffix=".exe") as tmp:
                installer_path = tmp.name

        # Setup wkhtmltopdf and get pdfkit configuration
        pdfkit_config = setup_wkhtmltopdf(config, installer_path)
        logging.info("wkhtmltopdf setup completed successfully.")
        
    except Exception as e:
        logging.error("Script failed: %s", e)
        cleanup(installer_path)
        sys.exit(1)
    finally:
        cleanup(installer_path)

if __name__ == "__main__":
    main()