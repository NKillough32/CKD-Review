import pandas as pd  # type: ignore
import numpy as np  # type: ignore
import os
import re
import csv
import sys 
import warnings
import logging
from datetime import datetime, timedelta
warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)
warnings.simplefilter(action='ignore', category=FutureWarning)

# Defined functions
def setup_logging(log_dir="logs"):
    """Configure logging with both file and console handlers"""
    # Create logs directory if it doesn't exist
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Create a timestamp for the log file name
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    log_file = os.path.join(log_dir, f'ckd_review_{timestamp}.log')

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

    return logging.getLogger(__name__)
# Removed redundant import for setup_logging
def check_files_exist(*file_paths):
    missing_files = [file for file in file_paths if not os.path.exists(file)]
    if missing_files:
        logger.info("\nThe following required files are missing:")
        for file in missing_files:
            logger.info(f"  - {file} (Missing)")
        logger.info("\nPlease add the required files to the directory.")
        
        # Wait for user input after adding the files
        for file in missing_files:
            input(f"Please add '{file}' to the directory for a full analysis, or press Enter to proceed with limited analysis...")
    else:
        logger.info("All required files are present.")
def preprocess_data(df):
    # Identify columns with 'Date' in the name
    date_columns = [col for col in df.columns if 'Date' in col]
    
    # Define a function to parse dates with multiple formats
    def parse_dates(date_str):
        if pd.isna(date_str):
            return pd.NaT
        for fmt in ("%d-%b-%y", "%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y"):
            try:
                return pd.to_datetime(date_str, format=fmt)
            except ValueError:
                continue
        return pd.NaT  # Return NaT if all formats fail
    
    # Apply date parsing to all date columns
    for date_col in date_columns:
        df[date_col] = df[date_col].apply(parse_dates)
    
    # Handle other preprocessing steps
    if 'Name, Dosage and Quantity' in df.columns:
        df.loc[:,'Name, Dosage and Quantity'] = df['Name, Dosage and Quantity'].astype(str)
    
    # Fill missing HC Number values forward
    if 'HC Number' in df.columns:
        df['HC Number'] = df['HC Number'].replace("", np.nan).ffill()
    
    return df
def update_df_with_newest_value2(df, group_col="HC Number"):
    # Convert date columns to datetime
    df['Date']   = pd.to_datetime(df['Date'],   errors='coerce')
    df['Date.2'] = pd.to_datetime(df['Date.2'], errors='coerce')

    # Treat empty or non-numeric 'Value' as missing
    df['Value'] = df['Value'].replace("", np.nan)
    df['Value'] = pd.to_numeric(df['Value'], errors='coerce')
    
    # Group by the specified column and identify the row with the newest Date.2 for each group
    newest_rows = {}
    for group, grp in df.groupby(group_col):
        # Filter to rows that have a valid Date.2
        grp_valid = grp[~grp['Date.2'].isna()]
        if grp_valid.empty:
            continue
        # Identify the row whose Date.2 is the most recent
        idx_newest = grp_valid['Date.2'].idxmax()
        newest_rows[group] = grp_valid.loc[idx_newest]

    # Helper to check "missing" in multiple senses
    def is_missing(val):
        if pd.isna(val):
            return True
        if isinstance(val, str):
            val = val.strip().lower()
            if not val or val in {'na', 'n/a', 'null', 'none'}:
                return True
        return False

    # Function to update a row if the original Date/Value is missing
    def update_row(row):
        group = row.get(group_col)
        if group not in newest_rows:
            return row  # No newest Date.2/Value.2 to pull from
        
        # The row we identified as having the most recent Date.2
        nr = newest_rows[group]
        
        # Only update if the original row's Value is missing
        if is_missing(row['Value']):
            row['Value'] = nr['Value.2']
        
        # Only update if the original row's Date is missing
        if is_missing(row['Date']):
            # Convert to a desired string format (dd/mm/YYYY) or leave it as datetime
            if pd.notna(nr['Date.2']):
                row['Date'] = nr['Date.2'].strftime('%d/%m/%Y')

        return row

    # Apply the row-level update
    df = df.apply(update_row, axis=1)
    return df
def select_closest_3m_prior_creatinine(row, df):
    # Ensure 'Date' is valid
    if pd.isna(row['Date']) or not isinstance(row['Date'], pd.Timestamp):
        return pd.Series([np.nan, np.nan], index=['Creatinine_3m_prior', 'Date_3m_prior'])

    target_date = row['Date'] - timedelta(days=90)

    hc_data = df[df['HC Number'] == row['HC Number']].copy()

    # Extract valid (Date.2, Value.2) pairs
    valid_pairs = hc_data[['Date.2', 'Value.2']].dropna().values.tolist()

    if not valid_pairs:
        return pd.Series([np.nan, np.nan], index=['Creatinine_3m_prior', 'Date_3m_prior'])

    closest_date = None
    closest_value = None
    min_diff = timedelta.max  # Initialize with the largest possible Timedelta

    for date, value in valid_pairs:
        diff = abs(date - target_date)
        if diff < min_diff:  # Now comparing Timedelta with Timedelta
            min_diff = diff
            closest_date = date
            closest_value = value

    return pd.Series([closest_value, closest_date], index=['Creatinine_3m_prior', 'Date_3m_prior'])
def summarize_medications(df):
    return (
        df.groupby('HC Number')['Name, Dosage and Quantity']
        .apply(lambda x: ', '.join(x.dropna()))
        .reset_index()
        .rename(columns={'Name, Dosage and Quantity': 'Medications'})
    )
def calculate_eGFR(Age, Gender, Creatinine, Height=None):
    if pd.isna(Age) or pd.isna(Gender) or pd.isna(Creatinine):
        return np.nan  # Return NaN if any input is missing

    Creatinine_mg_dL = Creatinine / 88.42  # Convert creatinine to mg/dL if in µmol/L
    
    if Age < 18:  # Use Bedside Schwartz for children
        if pd.isna(Height):  # Height is required for children
            return np.nan
        eGFR = (0.413 * Height) / Creatinine_mg_dL
    else:  # Use adult equation for 18+ (CKD-EPI)
        is_female = Gender == 'Female'
        K = 0.7 if is_female else 0.9
        alpha = -0.241 if is_female else -0.302
        female_multiplier = 1.012 if is_female else 1
        standardised_Scr = Creatinine_mg_dL / K
        eGFR = (142 * (min(standardised_Scr, 1)**alpha) * 
                (max(standardised_Scr, 1)**(-1.200)) * 
                (0.9938**Age) * female_multiplier)
    
    return eGFR
def classify_CKD_stage(eGFR):
    if pd.isna(eGFR):
        return None
    elif eGFR >= 90:
        return "Stage 1"
    elif eGFR >= 60:
        return "Stage 2"
    elif eGFR >= 45:
        return "Stage 3A"
    elif eGFR >= 30:
        return "Stage 3B"
    elif eGFR >= 15:
        return "Stage 4"
    elif 0 < eGFR < 15:
        return "Stage 5"
    else:
        return "No Data"
def calculate_egfr_trend(row):
    if pd.isna(row['eGFR']) or pd.isna(row['eGFR_3m_prior']) or pd.isna(row['Date']) or pd.isna(row['Date_3m_prior']):
        return "No Data"
    days_between = (row['Date'] - row['Date_3m_prior']).days
    if days_between == 0:
        return "No Data"
    annualized_change = (row['eGFR'] - row['eGFR_3m_prior']) * (365 / abs(days_between))
    if annualized_change < -5 or (row['eGFR_3m_prior'] > 0 and 
                                  (row['eGFR_3m_prior'] - row['eGFR']) / row['eGFR_3m_prior'] >= 0.25):
        return "Rapid Decline"
    return "Stable"
def classify_BP(systolic, diastolic):
    if pd.isna(systolic) or pd.isna(diastolic):
        return None
    elif systolic >= 180 or diastolic >= 120:
        return "Severe Hypertension"
    elif systolic >= 160 or diastolic >= 100:
        return "Stage 2 Hypertension"
    elif systolic >= 140 or diastolic >= 90:
        return "Stage 1 Hypertension"
    elif systolic < 140 and diastolic < 90:
        return "Normal"
    else:
        return None
def classify_CKD_ACR_grade(ACR):
    if ACR < 3:
        return "A1"
    elif ACR < 30:
        return "A2"
    else:
        return "A3"
def classify_anaemia(haemoglobin, gender):
    if pd.isna(haemoglobin):
        return None
    elif gender == "Male":
        if haemoglobin >= 130:
            return "Normal"
        elif haemoglobin >= 110:
            return "Mild Anaemia"
        elif haemoglobin >= 80:
            return "Moderate Anaemia"
        else:
            return "Severe Anaemia"
    elif gender == "Female":
        if haemoglobin >= 120:
            return "Normal"
        elif haemoglobin >= 110:
            return "Mild Anaemia"
        elif haemoglobin >= 80:
            return "Moderate Anaemia"
        else:
            return "Severe Anaemia"
    else:
        return None
def classify_potassium(potassium):
    if pd.isna(potassium):
        return "Missing"
    elif potassium > 5.5:
        return "Hyperkalemia"
    elif potassium < 3.5:
        return "Hypokalemia"
    else:
        return "Normal"
def classify_parathyroid(parathyroid):
    if pd.isna(parathyroid):
        return "Missing"
    elif parathyroid > 65:
        return "Elevated"
    elif parathyroid < 10:
        return "Low"
    else:
        return "Normal"
def classify_bicarbonate(bicarbonate):
    if pd.isna(bicarbonate):
        return "Missing"
    elif bicarbonate < 22:
        return "Low"
    elif bicarbonate > 29:
        return "High"
    else:
        return "Normal"
def classify_calcium(calcium):
    if pd.isna(calcium):
        return "Missing"
    elif calcium < 2.2:
        return "Hypocalcemia"
    elif calcium > 2.6:
        return "Hypercalcemia"
    else:
        return "Normal"
def classify_phosphate(phosphate):
    if pd.isna(phosphate):
        return "Missing"
    elif phosphate < 0.8:
        return "Hypophosphatemia"
    elif phosphate > 1.5:
        return "Hyperphosphatemia"
    else:
        return "Normal"
def classify_vitamin_d(vitamin_d):
    if pd.isna(vitamin_d):
        return "Missing"
    elif vitamin_d < 30:
        return "Deficient"
    elif vitamin_d < 50:
        return "Insufficient"
    else:
        return "Sufficient"
def classify_ckd_mbd(calcium_flag, phosphate_flag, parathyroid_flag):
    return "Check CKD-MBD" if calcium_flag != "Normal" or phosphate_flag != "Normal" or parathyroid_flag != "Normal" else "Normal"
def get_contraindicated_drugs(eGFR):
    contraindicated = []
    
    # Ensure eGFR is a valid number
    if pd.isna(eGFR):
        return contraindicated  # Return an empty list if eGFR is missing

    with open(contraindicated_drugs_file, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                drug_threshold = float(row['eGFR'])
                if eGFR <= drug_threshold:  # Safe comparison now
                    drug_name = row['contraindicated_drugs']
                    bnf_link = row.get('BNF_Link', '')  # Get BNF link if available
                    contraindicated.append((drug_name, bnf_link))  # Store as tuple
            except (ValueError, TypeError):
                continue  # Skip rows with invalid eGFR values

    return contraindicated
def check_contraindications(medications, contraindicated_list):
    prescribed_contraindicated = [
        f"{drug} ({link})" if link else drug  # Add link if available
        for drug, link in contraindicated_list 
        if re.search(r'\b' + re.escape(drug) + r'\b', medications, re.IGNORECASE)
    ]
    return ", ".join(prescribed_contraindicated) if prescribed_contraindicated else "No contraindications"
def recommended_medications(eGFR):
    if pd.isna(eGFR):
        return ["Unable to determine recommendations (Missing eGFR)"]
    
    if eGFR < 15:
        return [
            "Erythropoiesis-stimulating agents for anaemia (e.g., Epoetin alfa, Darbepoetin alfa, Methoxy polyethylene glycol-epoetin beta)",
            "Loop diuretics (e.g., Furosemide, Bumetanide, Torsemide) for fluid control",
            "Phosphate binders (e.g., Sevelamer, Lanthanum carbonate, Calcium acetate)",
            "Active vitamin D analogs (e.g., Alfacalcidol, Calcitriol, Paricalcitol)",
            "Sodium bicarbonate for metabolic acidosis management"
        ]
    elif eGFR < 30:
        return [
            "Statin (e.g., Atorvastatin, Rosuvastatin, Simvastatin)",
            "ACE inhibitors (e.g., Ramipril, Enalapril, Lisinopril) or ARBs (e.g., Losartan, Valsartan, Candesartan) (if not contraindicated) for proteinuria",
            "Erythropoiesis-stimulating agents for anaemia (e.g., Epoetin alfa, Darbepoetin alfa) (if indicated)",
            "Loop diuretics (e.g., Furosemide, Bumetanide, Torsemide) for fluid control"
        ]
    elif eGFR < 45:
        return [
            "Statin (e.g., Atorvastatin, Rosuvastatin, Simvastatin)",
            "ACE inhibitors (if not contraindicated) for proteinuria",
            "Phosphate binders (e.g., Sevelamer, Lanthanum carbonate, Calcium acetate)"
        ]
    elif eGFR < 60:
        return [
            "Statin (e.g., Atorvastatin, Rosuvastatin, Simvastatin)",
            "ACE inhibitors (if not contraindicated) for proteinuria",
            "Oral iron supplement (e.g., Ferrous sulfate, Ferrous gluconate, Ferrous fumarate) if needed"
        ]
    else:
        return [
            "Statin (e.g., Atorvastatin, Rosuvastatin, Simvastatin)",
            "ACE inhibitors (if not contraindicated) for proteinuria (if indicated)",
            "Lifestyle modifications"
        ]
def check_recommendations(medications, recommended):
    recommended_missing = []
    
    for drug in recommended:
        examples = re.split(r"[(),]", drug)
        examples = [example.strip() for example in examples if example.strip()]
        
        if not any(re.search(r'\b' + re.escape(example) + r'\b', medications, re.IGNORECASE) for example in examples):
            recommended_missing.append(drug)

    return ", ".join(recommended_missing)
def lifestyle_advice(ckd_stage):
    if ckd_stage in ["Stage 1", "Stage 2"]:
        return (
            "Encourage a balanced diet, including reduced sodium intake. "
            "Promote regular physical activity (150 minutes per week) as per general health guidance. "
            "Emphasize smoking cessation and maintaining a healthy weight."
        )
    elif ckd_stage in ["Stage 3A", "Stage 3B"]:
        return (
            "Encourage a balanced, low-sodium diet. Advise moderate, regular physical activity while monitoring for fatigue. "
            "Reinforce the importance of smoking cessation, weight management, and avoiding over-the-counter NSAIDs."
        )
    elif ckd_stage in ["Stage 4", "Stage 5"]:
        return (
            "Refer to a renal dietitian for specialist dietary guidance, focusing on protein and potassium intake. "
            "Advise on sodium restriction and safe physical activity within the patient's tolerance. "
            "Discuss advance care planning and monitor for anemia, acidosis, and hyperphosphatemia."
        )
    else:
        return (
            "Encourage general kidney health practices: a balanced, low-sodium diet; regular physical activity within comfort levels; "
            "smoking cessation; weight management; and regular health check-ups to monitor kidney function. "
            "Avoid over-the-counter NSAIDs and consult a healthcare provider for any new symptoms."
        )
def drug_adjustment(eGFR):
    adjustments = []
    
    # Ensure eGFR is a valid number
    if pd.isna(eGFR):
        return adjustments  # Return an empty list if eGFR is missing

    with open(drug_adjustment_file, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                drug_threshold = float(row['eGFR'])
                if eGFR <= drug_threshold:  # Safe comparison now
                    drug_name = row['drug_adjustment']
                    bnf_link = row.get('BNF_Link', '')  # Get BNF link if available
                    adjustments.append((drug_name, bnf_link))  # Store as tuple
            except (ValueError, TypeError):
                continue  # Skip rows with invalid eGFR values

    return adjustments
def check_dose_adjustments(medications, adjustment_list):
    prescribed_adjustments = [
        f"{drug} ({link})" if link else drug  # Add link if available
        for drug, link in adjustment_list 
        if re.search(r'\b' + re.escape(drug) + r'\b', medications, re.IGNORECASE)
    ]
    return ", ".join(prescribed_adjustments) if prescribed_adjustments else "No adjustments needed"
def check_all_contraindications(medications, contraindicated_list):
    prescribed_contraindicated = [
        f"{drug} ({link})" if link else drug  # Add BNF link if available
        for drug, link in contraindicated_list  # Extract drug name from tuple
        if re.search(r'\b' + re.escape(drug) + r'\b', medications, re.IGNORECASE)
    ]
    return ", ".join(prescribed_contraindicated) if prescribed_contraindicated else "No contraindications"
def parse_any_date(date_str):
    if pd.isna(date_str):
        return pd.NaT
    for fmt in ("%d-%b-%y", "%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y"):
        try:
            return pd.to_datetime(date_str, format=fmt)
        except ValueError:
            continue
    return pd.NaT  # Return NaT if all formats fail
def convert_date_columns(df):
    """Convert any column with 'Date' in its name to a Pandas datetime."""
    for col in df.columns:
        if 'Date' in col:
            df[col] = df[col].apply(parse_any_date)
    return df
def flag_aki(row):
    if any(pd.isna(x) for x in [row['Creatinine'], row['Creatinine_3m_prior'], row['Date'], row['Date_3m_prior']]):
        return "Insufficient Data"
    delta_creat = row['Creatinine'] - row['Creatinine_3m_prior']
    ratio = row['Creatinine'] / row['Creatinine_3m_prior']
    days = (row['Date'] - row['Date_3m_prior']).days
    if days <= 0 or days > 90:
        return "Invalid Timeframe"
    if ratio >= 3 or delta_creat >= 354:  # Stage 3
        return "AKI Stage 3 - Urgent"
    elif ratio >= 2:  # Stage 2
        return "AKI Stage 2 - Urgent"
    elif ratio >= 1.5 or delta_creat >= 26.5:  # Stage 1
        return "AKI Stage 1 - Review"
    return "No AKI"
def simple_cv_risk(age, gender, systolic_bp, hba1c, smoking=None):
    if any(pd.isna(x) for x in [age, gender, systolic_bp, hba1c]):
        return "Missing Data"
    score = 0
    score += 1 if age > 65 else 0
    score += 1 if systolic_bp > 140 else 0
    score += 1 if hba1c > 53 else 0
    score += 1 if smoking == "Yes" else 0
    return "High Risk" if score >= 3 else "Moderate Risk" if score >= 1 else "Low Risk"
def prioritize_patient(row):
    score = 0
    
    # Ensure risk_2yr is numeric, or default to NaN
    try:
        risk_2yr = float(row['risk_2yr'])  # Convert to float
    except ValueError:
        return "Unknown"  # If conversion fails, return 'Unknown'

    score += 2 if row['eGFR_Trend'] == "Rapid Decline" else 0
    score += 1 if risk_2yr > 20 else 0
    score += 1 if row['Proteinuria_Flag'].startswith("Immediate") else 0

    return "High" if score >= 3 else "Medium" if score >= 1 else "Low"

# Setup logging at the start of the script
logger = setup_logging()

# Replace this section:
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Get EMIS files path from environment variable
emis_path = os.getenv('EMIS_FILES_PATH')
if not emis_path:
    raise EnvironmentError("EMIS_FILES_PATH environment variable not set")

# Get Dependencies path from environment variable
dependencies_path = os.getenv('DEPENDENCIES_PATH')
if not dependencies_path:
    raise EnvironmentError("DEPENDENCIES_PATH environment variable not set")

# File paths - use emis_path for EMIS files
creatinine_file = os.path.join(emis_path, "Creatinine.csv")
CKD_check_file = os.path.join(emis_path, "CKD_check.csv")

# Use dependencies_path for all Dependencies files
contraindicated_drugs_file = os.path.join(dependencies_path, "contraindicated_drugs.csv")
drug_adjustment_file = os.path.join(dependencies_path, "drug_adjustment.csv")
statins_file = os.path.join(dependencies_path, "statins.csv")
surgery_info_file = os.path.join(dependencies_path, "surgery_information.csv")
template_dir = dependencies_path  # Remove the redundant "Dependencies" subfolder
diabetes_meds_file = os.path.join(dependencies_path, "diabetes_meds.csv")
sglt2_inhibitors_file = os.path.join(dependencies_path, "sglt2_inhibitors.csv")

# Output paths
CKD_review_file = os.path.join(os.getcwd(), "CKD_review.csv")
output_dir = os.path.join(os.getcwd(), "Patient_Summaries")

# Remove duplicate path definitions and verify required files
check_files_exist(
    creatinine_file, 
    CKD_check_file, 
    contraindicated_drugs_file, 
    drug_adjustment_file,
    statins_file,
    surgery_info_file,
    diabetes_meds_file,
    sglt2_inhibitors_file
)

# Load the data
creatinine = pd.read_csv(creatinine_file) if os.path.exists(creatinine_file) else pd.DataFrame()
CKD_check = pd.read_csv(CKD_check_file) if os.path.exists(CKD_check_file) else pd.DataFrame()

# Ensure 'HC Number' is properly forward-filled BEFORE applying the function
if not creatinine.empty:
    creatinine['HC Number'] = creatinine['HC Number'].replace("", np.nan).ffill()
if not CKD_check.empty:
    CKD_check['HC Number'] = CKD_check['HC Number'].replace("", np.nan).ffill()

# Replace empty strings with NaN
if not creatinine.empty:
    creatinine['Date'] = creatinine['Date'].replace('', np.nan)
if not CKD_check.empty:
    CKD_check['Date'] = CKD_check['Date'].replace('', np.nan)

# Use the function on each DataFrame
if not creatinine.empty:
    creatinine = convert_date_columns(creatinine)
if not CKD_check.empty:
    CKD_check = convert_date_columns(CKD_check)

# Apply the function to both datasets if needed
if not creatinine.empty:
    creatinine = update_df_with_newest_value2(creatinine)
if not CKD_check.empty:
    CKD_check = update_df_with_newest_value2(CKD_check)

# Apply function correctly by using a lambda function to pass 'df' explicitly
if not creatinine.empty:
    creatinine[['Creatinine_3m_prior', 'Date_3m_prior']] = creatinine.apply(
    lambda row: select_closest_3m_prior_creatinine(row, creatinine), axis=1
)
if not CKD_check.empty:
    CKD_check[['Creatinine_3m_prior', 'Date_3m_prior']] = CKD_check.apply(
    lambda row: select_closest_3m_prior_creatinine(row, CKD_check), axis=1
)

# Merge the aggregated lists back into the main datasets
if not creatinine.empty:
    medications_summary_creatinine = summarize_medications(creatinine)
    creatinine = creatinine.merge(medications_summary_creatinine, on="HC Number", how="left")
    creatinine["Code Term"] = "No EMIS CKD entry"
if not CKD_check.empty:
    medications_summary_ckd = summarize_medications(CKD_check)
    CKD_check = CKD_check.merge(medications_summary_ckd, on="HC Number", how="left")
    
# Remove rows with missing Age
if not creatinine.empty:
    creatinine = creatinine.loc[creatinine['Age'].notna()]
if not CKD_check.empty:    
    CKD_check = CKD_check.loc[CKD_check['Age'].notna()]

# Merge CKD_check and Creatinine based on HC Number, selecting only rows in Creatinine not present in CKD_check
# Prepare merged data based on available files
if not CKD_check.empty and not creatinine.empty:
    merged_data = pd.concat([CKD_check, creatinine[~creatinine['HC Number'].isin(CKD_check['HC Number'])]])
else:
    merged_data = CKD_check if not CKD_check.empty else creatinine  # Fallback to whichever file is available

# Allow mode selection at the end of the processing
mode = 'merged'  # Change to 'creatinine', 'ckd_check', or 'merged' as needed
if mode == 'creatinine' and not creatinine.empty:
    creatinine.to_csv("CKD_review.csv", index=False)
    CKD_review = creatinine
    logger.info("Creatinine data saved to CKD_review.csv")
elif mode == 'ckd_check' and not CKD_check.empty:
    CKD_check.to_csv("CKD_review.csv", index=False)
    CKD_review = CKD_check
    logger.info("CKD Check data saved to CKD_review.csv")
elif mode == 'merged' and not merged_data.empty:
    merged_data.to_csv("CKD_review.csv", index=False)
    CKD_review = merged_data
    logger.info("Merged data saved to CKD_review.csv")
else:
    logger.info("No data available for the selected mode.")
    CKD_review = pd.DataFrame()  # Define CKD_review as an empty DataFrame if no data is available

logger.info("Preprocessing data and performing CKD metrics calculations...")

# Confirm conversion of dates
CKD_review['Date'] = pd.to_datetime(CKD_review['Date'], errors='coerce')
CKD_review['Date.2'] = pd.to_datetime(CKD_review['Date.2'], errors='coerce')

CKD_review['Code Term'] = CKD_review['Code Term'].replace(['', None], 'EMIS CKD entry missing')

# Rename columns for clarity and consistency in the dataset
CKD_review.rename(
    columns={
        'Value': 'Creatinine',
        'Value.1': 'ACR',
        'Value.3': 'Systolic_BP',
        'Value.4': 'Diastolic_BP',
        'Value.5': 'haemoglobin',
        'Value.6': 'HbA1c',
        'Value.7': 'Potassium',
        'Value.8': 'Phosphate',
        'Value.9': 'Calcium',
        'Value.10': 'Vitamin_D',
        'Value.11': 'Height',
        'Value.12': 'Parathyroid',
        'Value.13': 'Bicarbonate',
        'Code Term': 'EMIS_CKD_Code',
        'Code Term.1': 'Transplant_Kidney',
        'Code Term.2': 'Dialysis'
    },
    inplace=True
)

# Replace missing ACR values with 0
CKD_review.loc[:,'ACR'] = CKD_review['ACR'].fillna(0)

# Ensure numeric types for Age and Creatinine
CKD_review['Creatinine'] = pd.to_numeric(CKD_review['Creatinine'], errors='coerce')
CKD_review['Age'] = pd.to_numeric(CKD_review['Age'], errors='coerce')
CKD_review['Gender'] = CKD_review['Gender'].astype('category')

# Apply eGFR calculation
CKD_review['eGFR'] = CKD_review.apply(
    lambda row: calculate_eGFR(row['Age'], row['Gender'], row['Creatinine'], row.get('Height', None)), axis=1
)
CKD_review['eGFR_3m_prior'] = CKD_review.apply(
    lambda row: calculate_eGFR(row['Age'], row['Gender'], row['Creatinine_3m_prior'], row.get('Height', None)), axis=1
)

# Ensure eGFR values are rounded to whole numbers, handling NA values safely
CKD_review['eGFR'] = CKD_review['eGFR'].apply(lambda x: round(x) if pd.notna(x) else pd.NA).astype('Int64')
CKD_review['eGFR_3m_prior'] = CKD_review['eGFR_3m_prior'].apply(lambda x: round(x) if pd.notna(x) else pd.NA).astype('Int64')

# Classify CKD Stages
CKD_review['CKD_Stage'] = CKD_review['eGFR'].apply(classify_CKD_stage)
CKD_review['CKD_Stage_3m'] = CKD_review['eGFR_3m_prior'].apply(classify_CKD_stage)

# Apply the function to the DataFrame
CKD_review['eGFR_Trend'] = CKD_review.apply(calculate_egfr_trend, axis=1)

# Step 1: Identify rows with missing data in any required column
required_columns = ['Age', 'Gender', 'eGFR', 'ACR']
missing_data_df = CKD_review[CKD_review[required_columns].isnull().any(axis=1)]

# Save subjects with missing data to a separate CSV
missing_data_df.to_csv("missing_data_subjects.csv", index=False)

# Remove subjects with missing data from the main DataFrame for KFRE calculations
CKD_review_complete = CKD_review.dropna(subset=required_columns).copy()

# Step 2: Constants and Centering Values
Age_mean = 7.036
Sex_mean = 0.5642
eGFR_mean = 7.222
ACR_ln_mean = 5.137

# Baseline survival rates
Baseline_survival_5yr = 0.9570
Baseline_survival_2yr = 0.9878

# Coefficients for 5-year and 2-year risks
coefficients = {
    'Age_coef': -0.2201,
    'Sex_coef': 0.2467,
    'eGFR_coef': 0.5567,
    'ACR_ln_coef': 0.4510
}

# Step 3: Process Complete Data for KFRE Calculations
# Map 'Gender' to binary 'sex' column and convert to float
gender_mapping = {'Male': 1, 'Female': 0}
CKD_review_complete['sex'] = CKD_review_complete['Gender'].map(gender_mapping)

# Drop rows with unexpected or missing 'Gender' values
CKD_review_complete = CKD_review_complete.dropna(subset=['sex'])

# Ensure 'sex' is a float
CKD_review_complete['sex'] = CKD_review_complete['sex'].astype(float)

# Adjust ACR to avoid math domain error (log of zero or negative)
CKD_review_complete['ACR'] = CKD_review_complete['ACR'].replace(0, 0.019)

# Centering variables
CKD_review_complete['Age_centered'] = (CKD_review_complete['Age'] / 10) - Age_mean
CKD_review_complete['Sex_centered'] = CKD_review_complete['sex'] - Sex_mean
CKD_review_complete['eGFR_centered'] = (CKD_review_complete['eGFR'] / 5) - eGFR_mean
CKD_review_complete['ACR_ln_centered'] = np.log(CKD_review_complete['ACR'] / 0.113) - ACR_ln_mean

# Linear predictor L for 5-year and 2-year risks
CKD_review_complete['L_5yr'] = (
    coefficients['Age_coef'] * CKD_review_complete['Age_centered'] +
    coefficients['Sex_coef'] * CKD_review_complete['Sex_centered'] -
    coefficients['eGFR_coef'] * CKD_review_complete['eGFR_centered'] +
    coefficients['ACR_ln_coef'] * CKD_review_complete['ACR_ln_centered']
)
CKD_review_complete['risk_5yr'] = 1 - (Baseline_survival_5yr) ** np.exp(CKD_review_complete['L_5yr'])

CKD_review_complete['L_2yr'] = (
    coefficients['Age_coef'] * CKD_review_complete['Age_centered'] +
    coefficients['Sex_coef'] * CKD_review_complete['Sex_centered'] -
    coefficients['eGFR_coef'] * CKD_review_complete['eGFR_centered'] +
    coefficients['ACR_ln_coef'] * CKD_review_complete['ACR_ln_centered']
)
CKD_review_complete['risk_2yr'] = 1 - (Baseline_survival_2yr) ** np.exp(CKD_review_complete['L_2yr'])

# Convert to percentages and round
CKD_review_complete['risk_2yr'] = (CKD_review_complete['risk_2yr'] * 100).round(2)
CKD_review_complete['risk_5yr'] = (CKD_review_complete['risk_5yr'] * 100).round(2)

# Step 4: Add Error Messages for Missing KFRE Calculations in missing_data_df
if not missing_data_df.empty:
    missing_data_df.loc[:, 'risk_5yr'] = "Error: Missing required values"
    missing_data_df.loc[:, 'risk_2yr'] = "Error: Missing required values"
    missing_data_df.loc[:, 'CKD_Stage'] = "Error: Insufficient data"
else:
    logger.info("Warning: missing_data_df is empty, skipping error message assignments.")

# Ensure missing_data_df exists and is a valid DataFrame
if 'missing_data_df' not in locals() or 'missing_data_df' not in globals():
    missing_data_df = pd.DataFrame()  # Create an empty DataFrame if not defined

# Step 5: Combine Complete and Missing DataFrames
final_CKD_review = pd.concat([CKD_review_complete, missing_data_df], ignore_index=True)

# Assign the final DataFrame back to CKD_review for further processing
CKD_review = final_CKD_review

# Classify BP
CKD_review.loc[:,'BP_Classification'] = CKD_review.apply(lambda row: classify_BP(row['Systolic_BP'], row['Diastolic_BP']), axis=1)
# Classify ACR
CKD_review.loc[:,'CKD_ACR'] = CKD_review['ACR'].apply(classify_CKD_ACR_grade)

# Adjust CKD Stage based on conditions
CKD_review.loc[:, 'CKD_Stage'] = CKD_review.apply(
    lambda row: "Normal Function" if pd.notna(row['ACR']) and pd.notna(row['eGFR']) and pd.notna(row['Date'])
                and row['ACR'] < 3 and row['eGFR'] > 60 
                else row['CKD_Stage'], 
    axis=1
)

CKD_review.loc[:, 'CKD_Stage_3m'] = CKD_review.apply(
    lambda row: "Normal Function" if pd.notna(row['ACR']) and pd.notna(row['eGFR']) and pd.notna(row['Date'])
                and row['ACR'] < 3 and row['eGFR'] > 60 
                else row['CKD_Stage_3m'], 
    axis=1
)

# Nephrology Referral
CKD_review.loc[:,'Nephrology_Referral'] = CKD_review.apply(
    lambda row: "Indicated on the basis of risk calculation" 
                if row['CKD_Stage'] in ["Stage 3A", "Stage 3B", "Stage 4", "Stage 5"] and row['risk_5yr'] >= 5 
                else "Not Indicated", 
    axis=1
)
CKD_review.loc[:,'Multidisciplinary_Care'] = CKD_review.apply(
    lambda row: "Indicated on the basis of risk calculation" 
                if row['CKD_Stage'] in ["Stage 3A", "Stage 3B", "Stage 4", "Stage 5"] and row['risk_2yr'] > 10 
                else "Not Indicated", 
    axis=1
)
CKD_review.loc[:,'Modality_Education'] = CKD_review.apply(
    lambda row: "Indicated on the basis of risk calculation" 
                if row['CKD_Stage'] in ["Stage 3A", "Stage 3B", "Stage 4", "Stage 5"] and row['risk_2yr'] > 40 
                else "Not Indicated", 
    axis=1
)

# Anaemia Classification
CKD_review.loc[:,'Anaemia_Classification'] = CKD_review.apply(lambda row: classify_anaemia(row['haemoglobin'], row['Gender']), axis=1)

# BP Target and Flag
CKD_review.loc[:, 'BP_Target'] = CKD_review.apply(
    lambda row: "<130/80" if pd.notna(row['ACR']) and row['ACR'] >= 70 
    else "<130/80" if pd.notna(row['HbA1c']) and row['HbA1c'] > 53 
    else "<140/90", axis=1
)

CKD_review.loc[:,'BP_Flag'] = CKD_review.apply(
    lambda row: "Above Target" if (
        ((row['Systolic_BP'] >= 140 or row['Diastolic_BP'] >= 90) and row['BP_Target'] == "<140/90") or 
        ((row['Systolic_BP'] >= 130 or row['Diastolic_BP'] >= 80) and row['BP_Target'] == "<130/80")
    ) else "On Target", 
    axis=1
)

# CKD-MBD Flags
CKD_review.loc[:,'Potassium_Flag'] = CKD_review['Potassium'].apply(classify_potassium)
CKD_review.loc[:,'Calcium_Flag'] = CKD_review['Calcium'].apply(classify_calcium)
CKD_review.loc[:,'Phosphate_Flag'] = CKD_review['Phosphate'].apply(classify_phosphate)
CKD_review.loc[:,'Bicarbonate_Flag'] = CKD_review['Bicarbonate'].apply(classify_bicarbonate)
CKD_review.loc[:,'Parathyroid_Flag'] = CKD_review['Parathyroid'].apply(classify_parathyroid)
CKD_review.loc[:,'Vitamin_D_Flag'] = CKD_review['Vitamin_D'].apply(classify_vitamin_d)
CKD_review.loc[:,'CKD_MBD_Flag'] = CKD_review.apply(
    lambda row: classify_ckd_mbd(row['Calcium_Flag'], row['Phosphate_Flag'], row['Parathyroid_Flag']),
    axis=1
)
# Proteinuria Flag
CKD_review.loc[:, 'Proteinuria_Flag'] = CKD_review.apply(
    lambda row: (
        "Immediate Referral - Severe Proteinuria (ACR ≥70)" if pd.notna(row['ACR']) and row['ACR'] >= 70 
        else "High Proteinuria - Urgent Referral (ACR 30-69)" if pd.notna(row['ACR']) and row['ACR'] >= 30 
        else "Raised Proteinuria - Consider Referral (ACR 3-29)" if pd.notna(row['ACR']) and row['ACR'] >= 3 
        else "Review Required (ACR Missing)" if pd.notna(row['ACR']) and row['ACR'] == 0.019 
        else "Review Required (ACR Missing)" if pd.isna(row['ACR'])  
        else "No Referral Needed"
    ), axis=1
)

# Contraindicated Medications
CKD_review.loc[:,'contraindicated_prescribed'] = CKD_review.apply(
    lambda row: check_contraindications(row['Medications'], get_contraindicated_drugs(row['eGFR'])), 
    axis=1
)
# Dose Adjustments
CKD_review.loc[:,'dose_adjustment_prescribed'] = CKD_review.apply(
    lambda row: check_dose_adjustments(row['Medications'], drug_adjustment(row['eGFR'])), 
    axis=1
)

# Statin Recommendation
# Read statins from the file and store them in a list
with open(statins_file, 'r') as file:
    statins = [line.strip() for line in file]

CKD_review.loc[:,'Statin_Recommendation'] = CKD_review.apply(
    lambda row: (
        "On Statin" if any(statin in row['Medications'] for statin in statins)
        else "Consider Statin" if row['eGFR'] < 60 or pd.isna(row['Medications'])
        else "Not on Statin"
    ),
    axis=1
)

CKD_review.loc[:,'Recommended_Medications'] = CKD_review.apply(
    lambda row: check_recommendations(row['Medications'], recommended_medications(row['eGFR'])), 
    axis=1
)

# Add current SGLT2i status check (add this after the above line)
def get_sglt2_medications():
    """Read SGLT2 inhibitors from dependency file"""
    medications = []
    with open(sglt2_inhibitors_file, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            medications.extend([row['medication'].lower(), row['brand_name'].lower()])
    return medications

def check_sglt2i_contraindications(row):
    """
    Check for SGLT2i contraindications based on eGFR and medications.
    """
    contraindications = []
    
    if pd.isna(row['eGFR']):
        return "Unable to assess - missing eGFR"
        
    if row['eGFR'] < 15:
        contraindications.append("eGFR < 15")
    elif row['eGFR'] < 25 and "dapagliflozin" not in str(row['Medications']).lower():
        contraindications.append("eGFR 15-25: only dapagliflozin suitable")
    
    diabetes_meds = get_diabetes_medications()
    has_diabetes = (
        any(med in str(row['Medications']).lower() for med in diabetes_meds) or 
        (pd.notna(row['HbA1c']) and row['HbA1c'] > 48)
    )
    
    if not has_diabetes and row['eGFR'] >= 30:
        contraindications.append("No diabetes diagnosis")
        
    return ", ".join(contraindications) if contraindications else "No contraindications"

def get_diabetes_medications():
    """
    Read diabetes medications from dependency file.
    Returns list of medication names and brand names in lowercase.
    """
    medications = []
    try:
        with open(diabetes_meds_file, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                medications.extend([
                    row['medication'].lower(),
                    row['brand_name'].lower() if row['brand_name'] else ''
                ])
        return list(set(filter(None, medications)))
    except Exception as e:
        logger.info(f"Error reading diabetes medications file: {e}")
        return []

# Update the recommend_sglt2 function
def recommend_sglt2(row):
    """
    Determine SGLT2 inhibitor recommendations based on NICE NG203 guidelines.
    """
    # Check for missing data
    if pd.isna(row['eGFR']) or pd.isna(row['ACR']):
        return "Unable to determine - Missing data"

    # Check contraindications
    contraindications = check_sglt2i_contraindications(row)
    if contraindications != "No contraindications":
        return f"Not recommended - {contraindications}"
    
    # Get diabetes status using file-based list
    diabetes_meds = get_diabetes_medications()
    has_diabetes = (
        any(med in str(row['Medications']).lower() for med in diabetes_meds) or 
        (pd.notna(row['HbA1c']) and row['HbA1c'] > 48)
    )

    # Check ACR thresholds
    meets_acr_threshold = (
        (has_diabetes and row['ACR'] >= 3) or
        (not has_diabetes and row['ACR'] >= 22.6)
    )

    if not meets_acr_threshold:
        return "Not indicated based on ACR threshold"

    # eGFR-based recommendations
    if row['eGFR'] >= 30:
        current_sglt2i = check_current_sglt2i(row['Medications'])
        if current_sglt2i:
            return f"Continue current SGLT2i ({current_sglt2i})"
        return "Recommend SGLT2i (dapagliflozin, empagliflozin, or canagliflozin)"
    elif row['eGFR'] >= 15:
        if "dapagliflozin" in str(row['Medications']).lower():
            return "Continue dapagliflozin"
        return "Consider dapagliflozin only"
    else:
        return "Not recommended - eGFR too low"

def check_current_sglt2i(medications):
    """
    Check which SGLT2i the patient is currently on.
    """
    if pd.isna(medications):
        return None
        
    medications_lower = str(medications).lower()
    sglt2i_meds = get_sglt2_medications()
    
    current = []
    for med in sglt2i_meds:
        if med in medications_lower:
            current.append(med)
            
    return ", ".join(current) if current else None

# Update the status check
CKD_review.loc[:,'Current_SGLT2i_Status'] = CKD_review['Medications'].apply(
    lambda x: "On SGLT2i" if any(med in str(x).lower() for med in get_sglt2_medications())
    else "Not on SGLT2i"
)

# Then, add this where you have the #SGLT2 Inhibitor Recommendation comment
CKD_review.loc[:,'SGLT2i_Recommendation'] = CKD_review.apply(recommend_sglt2, axis=1)

# Add these to the CKD_review DataFrame processing
CKD_review.loc[:,'SGLT2i_Contraindications'] = CKD_review.apply(check_sglt2i_contraindications, axis=1)
CKD_review.loc[:,'Current_SGLT2i'] = CKD_review['Medications'].apply(check_current_sglt2i)

# Update the SGLT2i action assessment
CKD_review.loc[:,'SGLT2i_Action_Needed'] = CKD_review.apply(
    lambda row: (
        "Continue current SGLT2i" if row['Current_SGLT2i_Status'] == "On SGLT2i" 
            and "recommend" in str(row['SGLT2i_Recommendation']).lower()
        else "Switch to dapagliflozin" if row['Current_SGLT2i_Status'] == "On SGLT2i" 
            and "dapagliflozin only" in str(row['SGLT2i_Recommendation']).lower()
        else "Consider initiating SGLT2i" if row['Current_SGLT2i_Status'] == "Not on SGLT2i" 
            and "recommend" in str(row['SGLT2i_Recommendation']).lower()
        else "Review/Stop current SGLT2i" if row['Current_SGLT2i_Status'] == "On SGLT2i" 
            and "not recommended" in str(row['SGLT2i_Recommendation']).lower()
        else "No action needed"
    ), 
    axis=1
)



# HbA1c Target
CKD_review.loc[:,'HbA1c_Target'] = CKD_review['HbA1c'].apply(
    lambda x: "Adjust Diabetes Management" if pd.notna(x) and x > 53 else "On Target" if pd.notna(x) else None
)

# Lifestyle Advice
CKD_review.loc[:,'Lifestyle_Advice'] = CKD_review['CKD_Stage'].apply(lifestyle_advice)

# Anaemia Flag
CKD_review.loc[:,'Anaemia_Flag'] = CKD_review['haemoglobin'].apply(
    lambda x: "Consider ESA/Iron" if pd.notna(x) and x < 110 else "No Action Needed"
)

# All Contraindications
CKD_review.loc[:,'All_Contraindications'] = CKD_review.apply(
    lambda row: check_all_contraindications(row['Medications'], get_contraindicated_drugs(row['eGFR'])), 
    axis=1
)

# AKI Flag
CKD_review['AKI_Flag'] = CKD_review.apply(flag_aki, axis=1)

# Calculate CV Risk
CKD_review['CV_Risk'] = CKD_review.apply(
    lambda row: simple_cv_risk(row['Age'], row['Gender'], row['Systolic_BP'], row['HbA1c']), axis=1
)

# Apply the function safely
CKD_review['Priority'] = CKD_review.apply(prioritize_patient, axis=1)

# Rename columns for clarity
CKD_review.rename(columns={
    'HC Number': 'HC_Number',
    'Date': 'Sample_Date',
    'Date.1': 'Sample_Date1',
    'Date_3m_prior': 'Sample_Date2',
    'Date.3': 'Sample_Date3',
    'Date.4': 'Sample_Date4',
    'Date.5': 'Sample_Date5',
    'Date.6': 'Sample_Date6',
    'Date.7': 'Sample_Date7',
    'Date.8': 'Sample_Date8',
    'Date.9': 'Sample_Date9',
    'Date.10': 'Sample_Date10',
    'Date.11': 'Sample_Date11',
    'Date.12': 'Sample_Date12',
    'Date.13': 'Sample_Date13',
    'Date.14': 'Sample_Date14',
    'Date.15': 'Sample_Date15',
}, inplace=True)

# Convert HC_Number to integer safely
CKD_review['HC_Number'] = pd.to_numeric(CKD_review['HC_Number'], errors='coerce').astype('Int64')

logger.info("Data preprocessing and metrics calculation complete.")
logger.info("Writing Output Data ...")
logger.info("Summary Statistics:")
logger.info(f"Patients with CKD Stage 3+: {len(CKD_review[CKD_review['CKD_Stage'].isin(['Stage 3A', 'Stage 3B', 'Stage 4', 'Stage 5'])])}")
logger.info(f"Patients with Contraindications: {len(CKD_review[CKD_review['contraindicated_prescribed'] != 'No contraindications'])}")
# Save output to CSV
output_file_name = f"eGFR_check_{pd.Timestamp.today().date()}.csv"
CKD_review.to_csv(output_file_name, index=False)

def check_ckd_changes(current_df):
    """
    Check for new CKD patients and staging changes by comparing with most recent historical data.
    
    Args:
        current_df: Current DataFrame with CKD data
    
    Returns:
        tuple: (new_patients_df, changed_staging_df)
    """
    # Get the Patient_Summaries directory
    summaries_dir = os.path.join(os.getcwd(), "Patient_Summaries")
    if not os.path.exists(summaries_dir):
        logger.info("No historical data found - Patient_Summaries directory doesn't exist")
        return pd.DataFrame(), pd.DataFrame()

    # Get all date folders
    date_folders = [d for d in os.listdir(summaries_dir) 
                   if os.path.isdir(os.path.join(summaries_dir, d))
                   and d != datetime.now().strftime("%Y-%m-%d")]
    
    if not date_folders:
        logger.info("No historical data folders found")
        return pd.DataFrame(), pd.DataFrame()

    # Get most recent date folder
    most_recent = max(date_folders)
    historical_file = os.path.join(summaries_dir, most_recent, f"data_check_{most_recent}.csv")
    
    if not os.path.exists(historical_file):
        logger.info(f"No data check file found in {most_recent} folder")
        return pd.DataFrame(), pd.DataFrame()

    try:
        # Read historical data
        historical_df = pd.read_csv(historical_file)
        
        # Ensure both DataFrames have required columns
        required_cols = ['HC_Number', 'CKD_Stage']
        if not all(col in current_df.columns for col in required_cols) or \
           not all(col in historical_df.columns for col in required_cols):
            logger.info("Required columns missing from data")
            return pd.DataFrame(), pd.DataFrame()

        # Convert HC_Number to same type in both DataFrames
        current_df['HC_Number'] = pd.to_numeric(current_df['HC_Number'], errors='coerce')
        historical_df['HC_Number'] = pd.to_numeric(historical_df['HC_Number'], errors='coerce')

        # Find new patients (in current but not in historical)
        new_patients = current_df[
            ~current_df['HC_Number'].isin(historical_df['HC_Number']) &
            (current_df['CKD_Stage'].notna()) &
            (current_df['CKD_Stage'] != "Normal Function")
        ]

        # Find patients with changed staging
        merged_df = current_df.merge(
            historical_df[['HC_Number', 'CKD_Stage']], 
            on='HC_Number', 
            how='inner',
            suffixes=('_current', '_historical')
        )
        
        changed_staging = merged_df[
            (merged_df['CKD_Stage_current'] != merged_df['CKD_Stage_historical']) &
            (merged_df['CKD_Stage_current'] != "Normal Function")
        ]

        # Save results to separate CSV files
        timestamp = datetime.now().strftime("%Y-%m-%d")
        if not new_patients.empty:
            new_patients.to_csv(f'new_ckd_patients_{timestamp}.csv', index=False)
            logger.info(f"Found {len(new_patients)} new CKD patients")
        
        if not changed_staging.empty:
            changed_staging.to_csv(f'changed_ckd_staging_{timestamp}.csv', index=False)
            logger.info(f"Found {len(changed_staging)} patients with changed CKD staging")

        return new_patients, changed_staging

    except Exception as e:
        logger.info(f"Error processing historical data: {str(e)}")
        return pd.DataFrame(), pd.DataFrame()

# Add this at the end of your main processing code, just before saving the output
logger.info("\nChecking for CKD staging changes...")
new_patients, changed_staging = check_ckd_changes(CKD_review)