import pandas as pd  # type: ignore
import numpy as np  # type: ignore
import os
import shutil
import warnings
import qrcode
import pathlib
from datetime import datetime
from jinja2 import Environment, FileSystemLoader  # type: ignore
warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)

# Get the current working directory
current_dir = os.getcwd()
surgery_info_file = os.path.join(current_dir,"Dependencies", "surgery_information.csv")

# Load data from CSV file
file_path = f"eGFR_check_{datetime.now().date()}.csv"
data = pd.read_csv(file_path)

# Ensure risk columns are numeric
data['risk_2yr'] = pd.to_numeric(data['risk_2yr'], errors='coerce')
data['risk_5yr'] = pd.to_numeric(data['risk_5yr'], errors='coerce')

def load_surgery_info(csv_path=surgery_info_file):
    """
    Load surgery information from CSV file
    Returns dictionary with surgery details
    """
    try:
        surgery_df = pd.read_csv(csv_path)
        # Convert first row to dictionary
        surgery_info = surgery_df.iloc[0].to_dict()
        return surgery_info
    except FileNotFoundError:
        print(f"Warning: Surgery information file not found at {csv_path}")
        return {}
    except Exception as e:
        print(f"Error reading surgery information: {str(e)}")
        return {}

# Function to generate QR code linking to CKD patient information
def generate_ckd_info_qr(output_path):
    """Generate QR code linking to CKD patient information"""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,  # Higher error correction
            box_size=10,
            border=4,
        )
        qr.add_data("https://patient.info/kidney-urinary-tract/chronic-kidney-disease-leaflet")
        qr.make(fit=True)
        qr_image = qr.make_image(fill_color="black", back_color="white")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Save with explicit format
        qr_image.save(output_path, format='PNG')
        
        print(f"QR code generated successfully at: {output_path}")
        return output_path
    except Exception as e:
        print(f"Error generating QR code: {e}")
        return None


# Modify generate_patient_html to save HTML reports
def generate_patient_html(data, template_dir=os.path.join(current_dir, "Dependencies"), output_dir="Patient_Summaries_HTML"):
    
    # Load surgery info at start of function
    surgery_info = load_surgery_info()

    # Format date columns to "YYYY-MM-DD" if present
    date_columns = [col for col in data.columns if "Date" in col]
    for date_col in date_columns:
        data[date_col] = pd.to_datetime(data[date_col], errors='coerce').dt.strftime("%Y-%m-%d")
    
        # Generate CKD info QR code once
    qr_filename = "ckd_info_qr.png"
    qr_path = os.path.join(current_dir, "Dependencies", qr_filename)
    generate_ckd_info_qr(qr_path)

    # Print debug information
    print(f"QR Code Path: {qr_path}")

    # Update patient data with absolute QR path
    for _, patient in data.iterrows():
        patient_data = patient.to_dict()
        patient_data.update(surgery_info)
        patient_data['qr_code_path'] = os.path.join(qr_path, qr_filename).replace('\\', '/')

    # Replace empty cells with "Missing" in all columns
    columns_to_replace = data.columns  
    data[columns_to_replace] = data[columns_to_replace].replace({
        "": "Missing",
        None: "Missing",
        pd.NA: "Missing",
        np.nan: "Missing"
    })

    # Convert numeric columns while preserving "Missing"
    numeric_columns = ['Phosphate', 'Calcium', 'Vitamin_D', 'Parathyroid', 'Bicarbonate']
    
    def convert_to_numeric(value):
        return float(value) if value != "Missing" else "Missing"
    
    for col in numeric_columns:
        data[col] = data[col].apply(convert_to_numeric)

    # Create the absolute path for output directory
    output_dir = os.path.abspath(output_dir)
    
    # Create date-stamped folder inside the output directory
    date_folder = os.path.join(output_dir, datetime.now().strftime("%Y-%m-%d"))
    os.makedirs(date_folder, exist_ok=True)
    
    # Set up Jinja2 environment to load HTML template
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("report_template.html")  # Template for patient summaries
    
# Loop through each patient's data and generate PDF
    for _, patient in data.iterrows():

        # Merge surgery info into patient data
        patient_data = patient.to_dict()
        patient_data.update(surgery_info)  # Add surgery details to the patient's data              
        patient_data['qr_code_path'] = pathlib.Path(qr_path).as_uri()
 
        # Print info message before generating report
        print(f"Generating HTML report for Patient HC_Number: {patient['HC_Number']}...")
        
        # Render the HTML content for each patient
        html_content = template.render(patient=patient_data)
        
        # Save the HTML file in the respective folder
        sanitized_review_folder = "".join([c if c.isalnum() or c.isspace() else "_" for c in patient['review_message']]).replace(" ", "_")
        review_folder = os.path.join(date_folder, sanitized_review_folder)
        os.makedirs(review_folder, exist_ok=True)

        file_name = os.path.join(review_folder, f"Patient_Summary_{patient['HC_Number']}.html")
        with open(file_name, 'w', encoding='utf-8') as file:
            file.write(html_content)
        
        # Print success message after saving the report
        print(f"HTML Report saved as Patient_Summary_{patient['HC_Number']}.html in {review_folder}")

    # Return the date folder path for further use
    return date_folder

# Load data from CSV file
file_path = f"eGFR_check_{datetime.now().date()}.csv"
data = pd.read_csv(file_path)

# Ensure risk columns are numeric
data['risk_2yr'] = pd.to_numeric(data['risk_2yr'], errors='coerce')
data['risk_5yr'] = pd.to_numeric(data['risk_5yr'], errors='coerce')

# Define review message based on NICE guideline criteria
def ckd_review(row):
    # Parse 'Sample_Date' to ensure it's in datetime format if not already
    eGFR_date = pd.to_datetime(row['Sample_Date'], errors='coerce').date() if pd.notna(row['Sample_Date']) else None

    # Convert CKD_ACR and risk_5yr to numeric values, handling non-numeric entries
    ACR = pd.to_numeric(row['ACR'], errors='coerce')
    risk_5yr = pd.to_numeric(row['risk_5yr'], errors='coerce')
    BP_Flag = row['BP_Flag']
    EMIS = row['EMIS_CKD_Code']

    # Check for incorrect EMIS coding
    if EMIS not in ["EMIS CKD entry missing", "No EMIS CKD entry"] and row['CKD_Stage'] == "Normal Function":
        return "Incorrect EMIS Coding"
    
    # Check if 'eGFR_date' is valid and calculate days since eGFR
    if eGFR_date:
        days_since_eGFR = (datetime.now().date() - eGFR_date).days
        
        # NICE guideline checks based on CKD stage and ACR
        if row['CKD_Stage'] in ["Stage 1", "Stage 2"]:
            if days_since_eGFR > 365 or ACR >= 3 or BP_Flag == "Above Target":
                return "Review Required (CKD Stage 1-2 with >1 year since last eGFR or ACR >3)"
            else:
                return "No immediate review required"
        elif row['CKD_Stage'] in ["Stage 3", "Stage 3A", "Stage 3B", "Stage 4", "Stage 5"]:
            if ACR >= 30 or risk_5yr > 5 or days_since_eGFR > 180:
                return "Review Required (CKD Stage 3-5 with >6 months since last eGFR, ACR >30, or high-risk)"
            elif days_since_eGFR > 90:
                return "Review Required (CKD Stage 3-5 with >3 months since last eGFR)"
            else:
                return "No immediate review required"
        else:
            return "Normal Renal Function"
    else:
        # Handle case where 'eGFR_date' is missing or invalid
        return "Review Required (eGFR date unavailable)"

# Apply review message function to add 'review_message' column
data['review_message'] = data.apply(ckd_review, axis=1)

print("Generating reports...")

# Function to rename folders based on mapping
def rename_folders(date_folder):
    # Define mapping with simpler names
    folder_mapping = {
        "Review_Required__CKD_Stage_1_2_with__1_year_since_last_eGFR_or_ACR__3_": "Stages_1-2_(12_Months_Review)",
        "No_immediate_review_required": "No_Immediate_Review",
        "Review_Required__CKD_Stage_3_5_with__6_months_since_last_eGFR__ACR__30__or_high_risk_": "Stages_3-5_(6_Months_Review)",
        "Review_Required__CKD_Stage_3_5_with__3_months_since_last_eGFR": "Stages_3-5_(3_Months_Review)",
        "Normal_Renal_Function": "Normal_Renal_Function",
        "Review_Required__eGFR_date_unavailable_": "Review_eGFR_Date_Unavailable"
    }
    
    # Verify that date_folder exists
    if not os.path.isdir(date_folder):
        print(f"Date folder not found: {date_folder}")
        return
    
    # List of existing folders in date_folder
    existing_folders = os.listdir(date_folder)
    
    # Attempt renaming by checking each folder in folder_mapping
    for original_name, new_name in folder_mapping.items():
        # Find folders that partially match the mapping keys
        for folder in existing_folders:
            if original_name in folder:
                original_path = os.path.join(date_folder, folder)
                new_path = os.path.join(date_folder, new_name)
                try:
                    os.rename(original_path, new_path)
                    print(f"Renamed folder '{folder}' to '{new_name}'")
                except Exception as e:
                    print(f"Failed to rename folder '{folder}' to '{new_name}': {e}")

# CKD stage and ACR grade codes for EMIS grouping
def get_ckd_stage_acr_group(row):
    eGFR = row['eGFR']
    ACR = row['ACR']

     # Check eGFR to determine the CKD stage
    if eGFR >= 90:
        if ACR < 3:
            return "Normal Function"
        elif ACR <= 30:
            return "Stage 1 A2"
        else:
            return "Stage 1 A3"
    elif eGFR >= 60:
        if ACR < 3:
            return "Normal Function"
        elif ACR <= 30:
            return "Stage 2 A2"
        else:
            return "Stage 2 A3"
    elif eGFR >= 45:
        if ACR < 3:
            return "Stage 3A A1"
        elif ACR <= 30:
            return "Stage 3A A2"
        else:
            return "Stage 3A A3"
    elif eGFR >= 30:
        if ACR < 3:
            return "Stage 3B A1"
        elif ACR <= 30:
            return "Stage 3B A2"
        else:
            return "Stage 3B A3"
    elif eGFR >= 15:
        if ACR < 3:
            return "Stage 4 A1"
        elif ACR <= 30:
            return "Stage 4 A2"
        else:
            return "Stage 4 A3"
    elif 0< eGFR < 15:
        if ACR < 3:
            return "Stage 5 A1"
        elif ACR <= 30:
            return "Stage 5 A2"
        else:
            return "Stage 5 A3"
    else:
        return "No Data"

# Apply the function to categorize patients
data['CKD_Group'] = data.apply(get_ckd_stage_acr_group, axis=1)

# Save each CKD group to a separate CSV for EMIS batch uploads
emis_clinical_code_dir = os.path.join(current_dir, "EMIS_Clinical_Code_Batch_Files")
os.makedirs(emis_clinical_code_dir, exist_ok=True)

# Generate batch files for each group
ckd_groups = data['CKD_Group'].unique()

for group in ckd_groups:
    # Filter patients in the current group
    filtered_patients = data[data['CKD_Group'] == group][["HC_Number"]].copy()
    filtered_patients.rename(columns={'HC_Number': 'HCN'}, inplace= True)

    # Generate the file path
    group_file_name = f"CKD_{group.replace(' ', '_').replace('-', '_')}_Patients.txt"
    group_file_path = os.path.join(emis_clinical_code_dir, group_file_name)
    
    # Save the batch file
    filtered_patients.to_csv(group_file_path, index=False, sep='\t', header=False)
    print(f"Saved {group} patients to: {group_file_path}")

# Save output to CSV
output_file_name2 = f"data_check_{pd.Timestamp.today().date()}.csv"
data.to_csv(output_file_name2, index=False)

# Function to move both the eGFR file and CKD_review file to the date-stamped folder
def move_ckd_files(date_folder):
    # Construct file names based on today's date
    egfr_file = f"eGFR_check_{pd.Timestamp.today().date()}.csv"
    data_file = f"data_check_{pd.Timestamp.today().date()}.csv"
    ckd_review_file = "CKD_review.csv"  # Static filename for CKD_review
    missing_KFRE_file = "missing_data_subjects.csv"

    # Construct source and destination paths for both files
    egfr_source = os.path.join(current_dir, egfr_file)
    egfr_destination = os.path.join(date_folder, egfr_file)
    
    data_source = os.path.join(current_dir, data_file)
    data_destination = os.path.join(date_folder, data_file)
    
    ckd_source = os.path.join(current_dir, ckd_review_file)
    ckd_destination = os.path.join(date_folder, ckd_review_file)

    missing_source = os.path.join(current_dir, missing_KFRE_file)
    missing_destination = os.path.join(date_folder, missing_KFRE_file)

   # Move the data file
    try:
        shutil.move(data_source, data_destination)
        print(f"Moved {data_file} to {date_folder}")
    except Exception as e:
        print(f"Failed to move {data_file}: {e}")
    
   # Move the eGFR file
    try:
        shutil.move(egfr_source, egfr_destination)
        print(f"Moved {egfr_file} to {date_folder}")
    except Exception as e:
        print(f"Failed to move {egfr_file}: {e}")
    
    # Move the CKD_review file
    try:
        shutil.move(ckd_source, ckd_destination)
        print(f"Moved {ckd_review_file} to {date_folder}")
    except Exception as e:
        print(f"Failed to move {ckd_review_file}: {e}")

    # Move the missing_KFRE file
    try:
        shutil.move(missing_source, missing_destination)
        print(f"Moved {missing_KFRE_file} to {date_folder}")
    except Exception as e:
        print(f"Failed to move {missing_KFRE_file}: {e}")

    # Move the EMIS Clinical Code Batch Files folder into the date-stamped folder
    try:
        emis_batch_destination = os.path.join(date_folder, "EMIS_Clinical_Code_Batch_Files")
        shutil.move(emis_clinical_code_dir, emis_batch_destination)
        print(f"Moved EMIS Clinical Code Batch Files to: {emis_batch_destination}")
    except Exception as e:
        print(f"Failed to move EMIS Clinical Code Batch Files: {e}")

# Function to delete specific CKD files after moving
def delete_ckd_files(date_folder):
    files_to_delete = [
        os.path.join(date_folder, f"eGFR_check_{pd.Timestamp.today().date()}.csv"),
        os.path.join(date_folder, "CKD_review.csv")
    ]

    for file_path in files_to_delete:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Deleted {file_path}")
            else:
                print(f"File not found for deletion: {file_path}")
        except Exception as e:
            print(f"Error deleting {file_path}: {e}")
            
# Run the functions in sequence
date_folder = generate_patient_html(data)  # Generate PDFs and capture the returned date folder path
rename_folders(date_folder)               # Rename folders within the date-stamped directory
move_ckd_files(date_folder)  # Moves both eGFR and CKD_review files to the date-stamped folder
delete_ckd_files(date_folder)             # Delete eGFR_check and CKD_review files
print("\nCKD Analysis and Reporting Completed ")
print(f"All reports and data saved in the folder: {date_folder}")
print("Please review missing file alerts above if applicable.\n")
