import os
import sys
import shutil
import ctypes
import logging
import hashlib
import tempfile
import subprocess
from datetime import datetime

import requests  # type: ignore
from tqdm import tqdm  # type: ignore
import pdfkit  # type: ignore

# --------------------------- Logging ---------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("wkhtmltopdf_setup.log", encoding="utf-8")]
)
log = logging.getLogger("wkhtmltopdf-setup")

# --------------------------- Config ----------------------------------
# Allow overrides via env vars
WKHTMLTOPDF_URL = os.environ.get(
    "WKHTMLTOPDF_URL",
    "https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox-0.12.6-1.msvc2015-win64.exe"
)
EXPECTED_SHA256 = os.environ.get("WKHTMLTOPDF_SHA256", "")  # optional; set if you pin a checksum
INSTALL_DIR = os.environ.get("WKHTMLTOPDF_INSTALL_DIR", r"C:\Program Files\wkhtmltopdf")
INSTALLER_NAME = "wkhtmltox-installer.exe"

# --------------------------- Helpers ---------------------------------
def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def elevate_and_exit():
    # Relaunch elevated and exit this (non-admin) process
    params = f'"{os.path.abspath(sys.argv[0])}"'
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
    if rc <= 32:
        log.error("UAC elevation failed (ShellExecute returned %s).", rc)
        sys.exit(1)
    sys.exit(0)

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def download_with_progress(url: str, dest_path: str, timeout: int = 60):
    log.info("Downloading wkhtmltopdf installer from %s", url)
    with requests.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        pbar = tqdm(total=total, unit="iB", unit_scale=True)
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))
        pbar.close()
    size = os.path.getsize(dest_path)
    log.info("Download complete (%d bytes).", size)
    if total and size != total:
        log.warning("Downloaded size (%d) != expected content-length (%d).", size, total)

def verify_checksum(path: str, expected_hex: str) -> bool:
    if not expected_hex:
        return True
    actual = sha256_file(path)
    if actual.lower() != expected_hex.lower():
        log.error("SHA-256 mismatch: expected %s, got %s", expected_hex, actual)
        return False
    log.info("SHA-256 verified.")
    return True

def run(cmd, **kwargs) -> subprocess.CompletedProcess:
    log.debug("Running: %s", " ".join([f'"{c}"' if " " in c else c for c in cmd]))
    return subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)

def which_wkhtmltopdf() -> str | None:
    # 1) env var override
    env_path = os.environ.get("WKHTMLTOPDF_PATH") or os.environ.get("WKHTMLTOPDF_BINARY")
    if env_path and os.path.isfile(env_path):
        return env_path

    # 2) on PATH
    from shutil import which
    p = which("wkhtmltopdf")
    if p:
        return p

    # 3) common install locations (64-bit first, then 32-bit)
    candidates = [
        r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
        r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
        os.path.join(INSTALL_DIR, "bin", "wkhtmltopdf.exe"),
        r"C:\ProgramData\chocolatey\bin\wkhtmltopdf.exe",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None

def install_silently(installer_path: str, install_dir: str):
    # NSIS-style /S silent; optionally force dir
    # Some builds accept /DIR="C:\Program Files\wkhtmltopdf"
    cmd = [installer_path, "/S", f'/DIR={install_dir}']
    log.info("Starting silent install to %s ...", install_dir)
    cp = run(cmd)
    if cp.returncode != 0:
        log.error("Silent install failed (code %s): %s", cp.returncode, cp.stderr.decode(errors="ignore"))
        return False
    log.info("Silent installation completed.")
    return True

def verify_binary(binary_path: str) -> bool:
    if not binary_path or not os.path.isfile(binary_path):
        return False
    cp = run([binary_path, "--version"])
    if cp.returncode != 0:
        log.error("wkhtmltopdf returned code %s: %s", cp.returncode, cp.stderr.decode(errors="ignore"))
        return False
    log.info("wkhtmltopdf detected: %s", cp.stdout.decode(errors="ignore").strip() or "OK")
    return True

def configure_pdfkit(binary_path: str) -> pdfkit.configuration:
    cfg = pdfkit.configuration(wkhtmltopdf=binary_path)
    # Smoke test: render a tiny HTML to PDF
    test_pdf = os.path.join(tempfile.gettempdir(), f"wkhtmltopdf_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
    try:
        pdfkit.from_string("<h1>Hello wkhtmltopdf</h1><p>Setup OK.</p>", test_pdf, configuration=cfg)
        if os.path.isfile(test_pdf) and os.path.getsize(test_pdf) > 0:
            log.info("pdfkit render test succeeded: %s", test_pdf)
        else:
            log.warning("pdfkit render test created an empty/absent file.")
    finally:
        try:
            if os.path.exists(test_pdf):
                os.remove(test_pdf)
        except Exception:
            pass
    return cfg

# --------------------------- Main ------------------------------------
def main():
    if os.name != "nt":
        log.error("This script is intended for Windows.")
        sys.exit(1)

    if not is_admin():
        log.info("Elevation required; relaunching with UAC prompt...")
        elevate_and_exit()

    # Detect existing installation first
    binary = which_wkhtmltopdf()
    if binary and verify_binary(binary):
        log.info("wkhtmltopdf already installed at: %s", binary)
        cfg = configure_pdfkit(binary)
        log.info("pdfkit configured successfully.")
        return

    # Download and install
    tmp_dir = tempfile.gettempdir()
    installer_path = os.path.join(tmp_dir, INSTALLER_NAME)

    if not os.path.exists(installer_path):
        try:
            download_with_progress(WKHTMLTOPDF_URL, installer_path)
        except Exception as e:
            log.error("Download failed: %s", e)
            sys.exit(1)

    if not verify_checksum(installer_path, EXPECTED_SHA256):
        sys.exit(1)

    if not install_silently(installer_path, INSTALL_DIR):
        # Fallback: open installer interactively
        log.warning("Opening installer interactively; please complete setup.")
        try:
            cp = run([installer_path])
            if cp.returncode not in (0, None):
                log.error("Interactive installer returned code %s", cp.returncode)
        except Exception as e:
            log.error("Failed to start interactive installer: %s", e)
            sys.exit(1)

    # Re-detect after install
    binary = which_wkhtmltopdf()
    if not verify_binary(binary or ""):
        log.error("Installation not detected or not working. Please check manually.")
        sys.exit(1)

    # Configure pdfkit and test
    try:
        _cfg = configure_pdfkit(binary)  # noqa: F841
        log.info("pdfkit configured successfully.")
    except Exception as e:
        log.error("Error configuring pdfkit: %s", e)
        sys.exit(1)

    # Cleanup installer
    try:
        if os.path.exists(installer_path):
            os.remove(installer_path)
            log.info("Installer removed: %s", installer_path)
    except Exception as e:
        log.warning("Could not remove installer: %s", e)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.warning("Interrupted by user.")
        sys.exit(1)
