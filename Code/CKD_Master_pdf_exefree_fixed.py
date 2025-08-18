import pandas as pd
import os
import warnings
import logging
import sys
import runpy
from datetime import datetime
import shutil

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler("pdf_generation.log")]
)

warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)

# Pin timestamp once to avoid rollover inconsistencies
RUN_TS = pd.Timestamp.now()
RUN_DATE = RUN_TS.date()
RUN_DATE_STR = RUN_TS.strftime("%Y-%m-%d")

# At the top with other path definitions, after the imports:
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
    # Use current working directory for dynamic files
    working_base_path = os.getcwd()
    emis_path = os.path.join(working_base_path, "EMIS_Files")
    dependencies_path = os.path.join(working_base_path, "Dependencies")
else:
    base_path = os.getcwd()
    working_base_path = base_path
    emis_path = os.path.join(base_path, "EMIS_Files")
    dependencies_path = os.path.join(base_path, "Dependencies")

# Set environment variables for other modules
os.environ['EMIS_FILES_PATH'] = emis_path
os.environ['DEPENDENCIES_PATH'] = dependencies_path

# Verify directories exist
for path, name in [(emis_path, "EMIS_Files"), (dependencies_path, "Dependencies")]:
    if not os.path.exists(path):
        logging.error(f"{name} directory not found at: {path}")
        logging.error(f"Please ensure {name} directory is present alongside the executable")
        sys.exit(1)

# Log EMIS directory contents
try:
    emis_contents = os.listdir(emis_path)
    logging.info(f"EMIS_Files contents: {emis_contents}")
except Exception as e:
    logging.error(f"Failed to list EMIS_Files contents: {e}")
    
# Execute the main CKD processing logic
logging.info("Starting CKD Data Analysis Pipeline....")
# Determine the path to CKD_core.py based on execution mode
ckd_core_path = (
    os.path.join(base_path, "CKD_core.py")
    if getattr(sys, 'frozen', False)
    else os.path.join(base_path, "Code", "CKD_core.py")
)

try:
    ns = runpy.run_path(ckd_core_path)  # executes as __main__ in its own dict
except FileNotFoundError:
    logging.error(f"CKD_core.py not found at {ckd_core_path}. Ensure it's included in the build.")
    sys.exit(1)

CKD_review = ns.get("CKD_review")
if CKD_review is None:
    logging.error("CKD_core did not produce CKD_review. Exiting.")
    sys.exit(1)

# Log the contents of working_base_path to confirm file generation by CKD_core.py
logging.info(f"Contents of working directory ({working_base_path}) after CKD_core.py execution:")
try:
    working_dir_contents = os.listdir(working_base_path)
    logging.info(f"Files/folders: {working_dir_contents}")
except Exception as e:
    logging.error(f"Failed to list contents of working directory: {e}")

# Import the PDF generation logic
from CKD_pdf_files_new import generate_patient_pdf

logging.info("Preprocessing data and performing CKD metrics calculations...")
logging.info("Data preprocessing and metrics calculation complete.")
logging.info("Writing Output Data and generating PDFs...")

# Generate patient PDFs
logging.info("Generating patient PDFs...")
date_folder = generate_patient_pdf(CKD_review)  # type: ignore
logging.info(f"date_folder returned by generate_patient_pdf: {date_folder}")
if not date_folder or not os.path.isdir(date_folder):
    logging.error(f"Invalid date_folder: {date_folder}. Patient summary folder not created.")
    sys.exit(1)

# Save output to CSV
output_file_name = os.path.join(working_base_path, f"eGFR_check_{RUN_DATE}.csv")
CKD_review.to_csv(output_file_name, index=False, encoding="utf-8-sig")  # type: ignore
logging.info(f"Saved output to {output_file_name}")
if not os.path.exists(output_file_name):
    logging.error(f"Failed to confirm existence of {output_file_name} after saving")

def safe_move(src, dst, name):
    """Safely move files/directories with error handling."""
    try:
        if not os.path.exists(src):
            logging.warning(f"Source file {src} does not exist, skipping")
            return
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        # On Python 3.8+, os.replace is atomic for files; for cross-type, fall back to shutil
        try:
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            elif os.path.isfile(dst):
                os.remove(dst)
        except Exception:
            pass
        shutil.move(src, dst)
        logging.info(f"Moved {name} to {dst}")
    except Exception as e:
        logging.error(f"Failed to move {name} from {src} to {dst}: {e}")

# Function to move files to the date-stamped folder
def move_ckd_files(date_folder):
    logging.info(f"Moving CKD files to {date_folder}")
    if not os.path.isdir(date_folder):
        logging.error(f"Cannot move files: {date_folder} is not a valid directory")
        return

    # CKD stage and ACR grade codes for EMIS grouping
    def get_ckd_stage_acr_group(row):
        eGFR = row['eGFR']
        ACR = row['ACR']

        if pd.isna(eGFR) or pd.isna(ACR):
            return "No Data"

        if eGFR >= 90:
            if ACR < 3: return "Normal Function"
            elif ACR <= 30: return "Stage 1 A2"
            else: return "Stage 1 A3"
        elif eGFR >= 60:
            if ACR < 3: return "Normal Function"
            elif ACR <= 30: return "Stage 2 A2"
            else: return "Stage 2 A3"
        elif eGFR >= 45:
            if ACR < 3: return "Stage 3A A1"
            elif ACR <= 30: return "Stage 3A A2"
            else: return "Stage 3A A3"
        elif eGFR >= 30:
            if ACR < 3: return "Stage 3B A1"
            elif ACR <= 30: return "Stage 3B A2"
            else: return "Stage 3B A3"
        elif eGFR >= 15:
            if ACR < 3: return "Stage 4 A1"
            elif ACR <= 30: return "Stage 4 A2"
            else: return "Stage 4 A3"
        elif 0 < eGFR < 15:
            if ACR < 3: return "Stage 5 A1"
            elif ACR <= 30: return "Stage 5 A2"
            else: return "Stage 5 A3"
        else:
            return "No Data"

    # Apply CKD grouping
    CKD_review['CKD_Group'] = CKD_review.apply(get_ckd_stage_acr_group, axis=1)  # type: ignore

    # Save EMIS batch files
    emis_dir = os.path.join(working_base_path, "EMIS_Clinical_Code_Batch_Files")
    os.makedirs(emis_dir, exist_ok=True)
    logging.info(f"Created EMIS batch files directory: {emis_dir}")
    for group in CKD_review['CKD_Group'].unique():  # type: ignore
        filtered_patients = CKD_review[CKD_review['CKD_Group'] == group][["HC_Number"]].copy()  # type: ignore
        # Don't cast patient identifiers to int - preserve as strings
        filtered_patients['HC_Number'] = filtered_patients['HC_Number'].astype(str).str.strip()
        filtered_patients = filtered_patients[filtered_patients['HC_Number'].ne("") & filtered_patients['HC_Number'].ne("nan")]
        filtered_patients.rename(columns={'HC_Number': 'HCN'}, inplace=True)
        group_file_name = f"CKD_{group.replace(' ', '_').replace('-', '_')}_Patients.txt"
        group_file_path = os.path.join(emis_dir, group_file_name)
        filtered_patients.to_csv(group_file_path, index=False, sep='\t', header=False, encoding="utf-8")
        logging.info(f"Saved {group} patients to: {group_file_path}")
        if not os.path.exists(group_file_path):
            logging.error(f"Failed to confirm existence of {group_file_path} after saving")

    # Save additional CSV
    output_file_name2 = os.path.join(working_base_path, f"data_check_{RUN_DATE}.csv")
    CKD_review.to_csv(output_file_name2, index=False, encoding="utf-8-sig")  # type: ignore
    logging.info(f"Saved output to {output_file_name2}")
    if not os.path.exists(output_file_name2):
        logging.error(f"Failed to confirm existence of {output_file_name2} after saving")

    # Construct file names based on RUN_DATE
    egfr_file = f"eGFR_check_{RUN_DATE}.csv"
    data_file = f"data_check_{RUN_DATE}.csv"
    ckd_review_file = "CKD_review.csv"
    missing_KFRE_file = "missing_data_subjects.csv"
    new_ckd_file = f"new_ckd_patients_{RUN_DATE}.csv"
    changed_staging_file = f"changed_ckd_staging_{RUN_DATE}.csv"

    # Log the existence of each source file
    logging.info(f"Checking for source files in {working_base_path}:")
    for src, name in [
        (os.path.join(working_base_path, egfr_file), egfr_file),
        (os.path.join(working_base_path, data_file), data_file),
        (os.path.join(working_base_path, ckd_review_file), ckd_review_file),
        (os.path.join(working_base_path, missing_KFRE_file), missing_KFRE_file)
    ]:
        if os.path.exists(src):
            logging.info(f"Found {name} at {src}")
        else:
            logging.warning(f"{name} not found at {src}")

    # Move files with error handling using safe_move
    for src_name, dst_name in [
        (data_file, data_file),
        (egfr_file, egfr_file),
        (ckd_review_file, ckd_review_file),
        (missing_KFRE_file, missing_KFRE_file),
        (new_ckd_file, new_ckd_file),
        (changed_staging_file, changed_staging_file)
    ]:
        src = os.path.join(working_base_path, src_name)
        dst = os.path.join(date_folder, dst_name)
        safe_move(src, dst, src_name)

    # Move the EMIS_Clinical_Code_Batch_Files folder
    emis_source = os.path.join(working_base_path, "EMIS_Clinical_Code_Batch_Files")
    emis_destination = os.path.join(date_folder, "EMIS_Clinical_Code_Batch_Files")
    safe_move(emis_source, emis_destination, "EMIS_Clinical_Code_Batch_Files")

def rename_folders(date_folder):
    """Rename folders to match current review folder names."""
    logging.info(f"Renaming folders in {date_folder}")
    # Map created by map_review_message_to_folder(...) in CKD_pdf_files_new
    folder_mapping = {
        "Review_Stage1_2_ACR3":           "Stages_1-2_ACR>=3",
        "Review_Stage3_5_eGFR30":         "Stages_3-5_eGFR<30",
        "Review_Stage3_5_ACR30":          "Stages_3-5_ACR>=30",
        "Review_Stage3_5_Risk5":          "Stages_3-5_KFRE5y>5pct",
        "Review_eGFR_Unavailable":        "Review_eGFR_Unavailable",
        "No_Immediate_Review":            "No_Immediate_Review",
        "General_Review_Stage1_2":        "General_Review_Stages_1-2",
        "General_Review_Stage3_5":        "General_Review_Stages_3-5",
        "General_Review_Unknown":         "General_Review_Unknown",
    }
    if not os.path.isdir(date_folder):
        logging.warning(f"Date folder not found: {date_folder}")
        return

    for folder in os.listdir(date_folder):
        src = os.path.join(date_folder, folder)
        if not os.path.isdir(src):
            continue
        for key, new_name in folder_mapping.items():
            if folder == key or key in folder:
                dst = os.path.join(date_folder, new_name)
                try:
                    if os.path.abspath(src) != os.path.abspath(dst):
                        os.replace(src, dst)
                        logging.info(f"Renamed '{folder}' -> '{new_name}'")
                except Exception as e:
                    logging.error(f"Failed to rename '{folder}' to '{new_name}': {e}")
                break

# File deletion function
def delete_ckd_files(date_folder):
    logging.info(f"Deleting CKD files in {date_folder}")
    files_to_delete = [
        os.path.join(date_folder, f"eGFR_check_{RUN_DATE}.csv"),
        os.path.join(date_folder, "CKD_review.csv")
    ]
    for file_path in files_to_delete:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logging.info(f"Deleted {file_path}")
            else:
                logging.warning(f"File not found for deletion: {file_path}")
        except Exception as e:
            logging.error(f"Error deleting {file_path}: {e}")

# Execute the pipeline
move_ckd_files(date_folder)
rename_folders(date_folder)
delete_ckd_files(date_folder)

# Log the contents of date_folder for debugging
logging.info(f"Contents of date_folder ({date_folder}) after pipeline execution:")
try:
    date_folder_contents = os.listdir(date_folder)
    logging.info(f"Files/folders: {date_folder_contents}")
except Exception as e:
    logging.error(f"Failed to list contents of date_folder: {e}")

logging.info("\nCKD Analysis and Reporting Completed")
logging.info(f"All reports and data saved in the folder: {date_folder}")
logging.info("Please review missing file alerts above if applicable.\n")

# Add analysis script execution
logging.info("Running statistical analysis...")

# Ensure analysis_script is importable
code_dir = os.path.join(base_path, "Code")
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)

try:
    from analysis_script import analyze_ckd_data, print_results, save_results
except Exception as e:
    logging.error(f"Unable to import analysis_script from {code_dir}: {e}")
    analyze_ckd_data = print_results = save_results = None

if analyze_ckd_data and print_results and save_results:
    # Construct filepath for analysis input
    analysis_input = os.path.join(date_folder, f"data_check_{RUN_DATE}.csv")
    
    if os.path.exists(analysis_input):
        try:
            # Run analysis
            results = analyze_ckd_data(analysis_input)
            
            # Save results to file
            analysis_output = os.path.join(date_folder, f"analysis_results_{RUN_DATE}.txt")
            save_results(results, analysis_output)
            
            # Print results to console
            print_results(results)
            
            logging.info(f"Analysis results saved to: {analysis_output}")
        except Exception as e:
            logging.error(f"Error running analysis: {e}")
    else:
        logging.error(f"Analysis input file not found: {analysis_input}")
else:
    logging.warning("Analysis script not available, skipping statistical analysis")

logging.info("Analysis complete.")
