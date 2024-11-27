import pandas as pd  # type: ignore
import numpy as np  # type: ignore
import os
import re
import csv
import shutil
import subprocess
import requests  # type: ignore
from datetime import datetime, timedelta
from jinja2 import Environment, FileSystemLoader  # type: ignore

# Get the current working directory
current_dir = os.getcwd()

# Set up relative paths for data and output files
creatinine_file = os.path.join(current_dir, "Creatinine.csv")
CKD_check_file = os.path.join(current_dir, "CKD_check.csv")
CKD_review_file = os.path.join(current_dir, "CKD_review.csv")
contraindicated_drugs_file = os.path.join(current_dir, "contraindicated_drugs.csv")
drug_adjustment_file = os.path.join(current_dir, "drug_adjustment.csv")
template_dir = current_dir  # Assuming template file is in current folder
output_dir = os.path.join(current_dir, "Patient_Summaries")  # Output directory for PDFs

def check_files_exist(*file_paths):
    missing_files = [file for file in file_paths if not os.path.exists(file)]
    if missing_files:
        print("\nThe following required files are missing:")
        for file in missing_files:
            print(f"  - {file} (Missing)")
        print("\nPlease add the required files to the directory.")
        
        # Wait for user input after adding the files
        for file in missing_files:
            input(f"Please add '{file}' to the directory for a full analysis, or press Enter to proceed with limited analysis...")
    else:
        print("All required files are present.")

check_files_exist(creatinine_file, CKD_check_file, contraindicated_drugs_file, drug_adjustment_file)

print("Starting CKD Data Analysis Pipeline....")

# Load the data
creatinine = pd.read_csv(creatinine_file) if os.path.exists(creatinine_file) else pd.DataFrame()
CKD_check = pd.read_csv(CKD_check_file) if os.path.exists(CKD_check_file) else pd.DataFrame()

def preprocess_data(df):
    # Identify columns with 'Date' in the name
    date_columns = [col for col in df.columns if 'Date' in col]
    
    # Define a function to parse dates with multiple formats
    def parse_dates(date_str):
        if pd.isna(date_str):
            return pd.NaT
        for fmt in ("%d-%b-%y", "%Y-%m-%d", "%d/%m/%Y"):
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
        df['Name, Dosage and Quantity'] = df['Name, Dosage and Quantity'].astype(str)
    
    # Fill missing HC Number values forward
    if 'HC Number' in df.columns:
        df['HC Number'] = df['HC Number'].replace("", np.nan).ffill()
    
    return df

# Apply preprocessing to both datasets
if not creatinine.empty:
    creatinine = preprocess_data(creatinine)
if not CKD_check.empty:
    CKD_check = preprocess_data(CKD_check)

# Function to select the closest 3-month prior creatinine value
def select_closest_3m_prior_creatinine(row):
    three_month_threshold = timedelta(days=90)
    
    prior_dates = [row.get('Date.2')]
    prior_values = [row.get('Value.2')]
    
    valid_prior_dates = [date for date in prior_dates if pd.notna(date)]
    valid_prior_values = [prior_values[i] for i, date in enumerate(prior_dates) if pd.notna(date)]
    
    if not pd.notna(row.get('Date')) or not valid_prior_dates:
        return np.nan
    
    differences = [abs((row['Date'] - date) - three_month_threshold) for date in valid_prior_dates]
    min_diff_index = differences.index(min(differences))
    
    return valid_prior_values[min_diff_index]

# Apply the function to both datasets if needed
if not creatinine.empty:
    creatinine['Creatinine_3m_prior'] = creatinine.apply(select_closest_3m_prior_creatinine, axis=1)
if not CKD_check.empty:
    CKD_check['Creatinine_3m_prior'] = CKD_check.apply(select_closest_3m_prior_creatinine, axis=1)

# Summarise medications by HC Number, renaming the result to avoid conflicts
def summarize_medications(df):
    return (
        df.groupby('HC Number')['Name, Dosage and Quantity']
        .apply(lambda x: ', '.join(x.dropna()))
        .reset_index()
        .rename(columns={'Name, Dosage and Quantity': 'Medications'})
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
    creatinine.dropna(subset=['Age'], inplace=True)
if not CKD_check.empty:    
    CKD_check.dropna(subset=['Age'], inplace=True)

# Merge CKD_check and Creatinine based on HC Number, selecting only rows in Creatinine not present in CKD_check
# Prepare merged data based on available files
if not CKD_check.empty and not creatinine.empty:
    merged_data = pd.concat([CKD_check, creatinine[~creatinine['HC Number'].isin(CKD_check['HC Number'])]])
else:
    merged_data = CKD_check if not CKD_check.empty else creatinine  # Fallback to whichever file is available

# Allow mode selection at the end of the processing
mode = 'merged'  # Change to 'creatinine', 'ckd_check', or 'merged' as needed

# Select the dataset to save based on mode
if mode == 'creatinine' and not creatinine.empty:
    creatinine.to_csv("CKD_review.csv", index=False)
    print("Creatinine data saved to CKD_review.csv")
elif mode == 'ckd_check' and not CKD_check.empty:
    CKD_check.to_csv("CKD_review.csv", index=False)
    print("CKD Check data saved to CKD_review.csv")
elif mode == 'merged' and not merged_data.empty:
    merged_data.to_csv("CKD_review.csv", index=False)
    print("Merged data saved to CKD_review.csv")
else:
    print("No data available for the selected mode.")

# Optional: Further processing on the final merged dataset (if needed)
if not os.path.exists(CKD_review_file):
    raise FileNotFoundError(f"{CKD_review_file} not found.")
CKD_review = pd.read_csv(CKD_review_file)

print("Preprocessing data and performing CKD metrics calculations...")

# Confirm conversion of dates
CKD_review['Date'] = pd.to_datetime(CKD_review['Date'], errors='coerce')
CKD_review['Date.2'] = pd.to_datetime(CKD_review['Date.2'], errors='coerce')

# Rename columns for clarity
CKD_review.rename(columns={
    'Value': 'Creatinine', 'Value.1': 'ACR',
    'Value.3': 'Systolic_BP', 'Value.4': 'Diastolic_BP', 'Value.5': 'haemoglobin',
    'Value.6': 'HbA1c', 'Value.7': 'Potassium', 'Value.8': 'Phosphate',
    'Value.9': 'Calcium', 'Value.10': 'Vitamin_D', 'Code Term': 'EMIS_CKD_Code', 'Value.11': 'Height'
}, inplace=True)

# Replace missing ACR values with 0
CKD_review['ACR'] = CKD_review['ACR'].fillna(0)

# Handle empty date fields by replacing with "Missing value"
for col in ['Date', 'Date.1', 'Date.2', 'Date.3', 'Date.4', 'Date.5', 'Date.6', 'Date.7', 'Date.8', 'Date.9', 'Date.10']:
    CKD_review[col] = CKD_review[col].replace("", "Missing value")

# Ensure numeric types for Age and Creatinine
CKD_review['Creatinine'] = pd.to_numeric(CKD_review['Creatinine'], errors='coerce')
CKD_review['Age'] = pd.to_numeric(CKD_review['Age'], errors='coerce')
CKD_review['Gender'] = CKD_review['Gender'].astype('category')

# eGFR Calculation function
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

# Apply eGFR calculation
CKD_review['eGFR'] = CKD_review.apply(
    lambda row: calculate_eGFR(row['Age'], row['Gender'], row['Creatinine'], row.get('Height', None)), axis=1
)
CKD_review['eGFR_3m_prior'] = CKD_review.apply(
    lambda row: calculate_eGFR(row['Age'], row['Gender'], row['Creatinine_3m_prior'], row.get('Height', None)), axis=1
)

# CKD Stage classification
def classify_CKD_stage(eGFR):
    if pd.isna(eGFR):
        return None
    elif eGFR >= 90:
        return "Stage 1"
    elif eGFR >= 60:
        return "Stage 2"
    elif eGFR >= 45:
        return "Stage 3a"
    elif eGFR >= 30:
        return "Stage 3b"
    elif eGFR >= 15:
        return "Stage 4"
    else:
        return "Stage 5"

CKD_review['CKD_Stage'] = CKD_review['eGFR'].apply(classify_CKD_stage)
CKD_review['CKD_Stage_3m'] = CKD_review['eGFR_3m_prior'].apply(classify_CKD_stage)

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
CKD_review_complete['ACR'] = CKD_review_complete['ACR'].replace(0, 0.01)

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
missing_data_df.loc[:, 'risk_5yr'] = "Error: Missing required values"
missing_data_df.loc[:, 'risk_2yr'] = "Error: Missing required values"
missing_data_df.loc[:, 'CKD_Stage'] = "Error: Insufficient data"

# Step 5: Combine Complete and Missing DataFrames
final_CKD_review = pd.concat([CKD_review_complete, missing_data_df], ignore_index=True)

# Assign the final DataFrame back to CKD_review for further processing
CKD_review = final_CKD_review

# BP classification
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

# Classify BP
CKD_review['BP_Classification'] = CKD_review.apply(lambda row: classify_BP(row['Systolic_BP'], row['Diastolic_BP']), axis=1)

# CKD-ACR Grade Classification
def classify_CKD_ACR_grade(ACR):
    if ACR <= 3:
        return "A1"
    elif ACR < 30:
        return "A2"
    else:
        return "A3"

CKD_review['CKD_ACR'] = CKD_review['ACR'].apply(classify_CKD_ACR_grade)

# Adjust CKD Stage based on conditions
CKD_review['CKD_Stage'] = CKD_review.apply(
    lambda row: "Normal Function" if row['ACR'] <= 3 and row['eGFR'] > 60 and row['Date'] != "" else row['CKD_Stage'], 
    axis=1
)
CKD_review['CKD_Stage'] = CKD_review.apply(
    lambda row: "Normal/Stage1" if row['CKD_Stage'] == "Stage 1" and row['Date'] == "" else row['CKD_Stage'], 
    axis=1
)

# Nephrology Referral
CKD_review['Nephrology_Referral'] = CKD_review.apply(
    lambda row: "Indicated on the basis of risk calculation" 
                if row['CKD_Stage'] in ["Stage 3a", "Stage 3b", "Stage 4", "Stage 5"] and row['risk_5yr'] >= 5 
                else "Not Indicated", 
    axis=1
)
CKD_review['Multidisciplinary_Care'] = CKD_review.apply(
    lambda row: "Indicated on the basis of risk calculation" 
                if row['CKD_Stage'] in ["Stage 3a", "Stage 3b", "Stage 4", "Stage 5"] and row['risk_2yr'] > 10 
                else "Not Indicated", 
    axis=1
)
CKD_review['Modality_Education'] = CKD_review.apply(
    lambda row: "Indicated on the basis of risk calculation" 
                if row['CKD_Stage'] in ["Stage 3a", "Stage 3b", "Stage 4", "Stage 5"] and row['risk_2yr'] > 40 
                else "Not Indicated", 
    axis=1
)

# Check for "Normal Function" in CKD_Stage_3m and overwrite CKD_Stage with "Acute Kidney Injury"
CKD_review['CKD_Stage'] = CKD_review.apply(
    lambda row: "Acute Kidney Injury" if row['CKD_Stage_3m'] == "Normal Function" else row['CKD_Stage'],
    axis=1
)

# Anemia Classification
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

CKD_review['Anaemia_Classification'] = CKD_review.apply(lambda row: classify_anaemia(row['haemoglobin'], row['Gender']), axis=1)

# BP Target and Flag
CKD_review['BP_Target'] = CKD_review.apply(
    lambda row: "<130/80" if row['ACR'] >= 70 or not pd.isna(row['HbA1c']) else "<140/90", 
    axis=1
)
CKD_review['BP_Flag'] = CKD_review.apply(
    lambda row: "Above Target" if (
        ((row['Systolic_BP'] >= 140 or row['Diastolic_BP'] >= 90) and row['BP_Target'] == "<140/90") or 
        ((row['Systolic_BP'] >= 130 or row['Diastolic_BP'] >= 80) and row['BP_Target'] == "<130/80")
    ) else "On Target", 
    axis=1
)

# Potassium, Calcium, and Phosphate Flags
def classify_potassium(potassium):
    if pd.isna(potassium):
        return "Missing"
    elif potassium > 5.5:
        return "Hyperkalemia"
    elif potassium < 3.5:
        return "Hypokalemia"
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

CKD_review['Potassium_Flag'] = CKD_review['Potassium'].apply(classify_potassium)
CKD_review['Calcium_Flag'] = CKD_review['Calcium'].apply(classify_calcium)
CKD_review['Phosphate_Flag'] = CKD_review['Phosphate'].apply(classify_phosphate)

def classify_ckd_mbd(calcium_flag, phosphate_flag):
    return "Check CKD-MBD" if calcium_flag != "Normal" or phosphate_flag != "Normal" else "Normal"

CKD_review['CKD_MBD_Flag'] = CKD_review.apply(
    lambda row: classify_ckd_mbd(row['Calcium_Flag'], row['Phosphate_Flag']),
    axis=1
)

# Proteinuria Flag
CKD_review['Proteinuria_Flag'] = CKD_review.apply(
    lambda row: "Persistent Proteinuria - Consider Referral" if row['ACR'] >= 3 and row['eGFR'] > 60 else "No Referral Needed", 
    axis=1
)

# Contraindicated Medications
def get_contraindicated_drugs(eGFR):
    contraindicated = []
    with open(contraindicated_drugs_file, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if float(row['eGFR']) >= eGFR:
                contraindicated.append(row['contraindicated_drugs'])
    return contraindicated

def check_contraindications(medications, contraindicated):
    prescribed_contraindicated = [drug for drug in contraindicated if re.search(r'\b' + re.escape(drug) + r'\b', medications, re.IGNORECASE)]
    return ", ".join(prescribed_contraindicated) if prescribed_contraindicated else "No contraindications"

CKD_review['contraindicated_prescribed'] = CKD_review.apply(
    lambda row: check_contraindications(row['Medications'], get_contraindicated_drugs(row['eGFR'])), 
    axis=1
)

# Statin Recommendation
statins = ["Atorvastatin", "Simvastatin", "Rosuvastatin", "Pravastatin", "Fluvastatin", "Pitavastatin"]

CKD_review['Statin_Recommendation'] = CKD_review.apply(
    lambda row: (
        "On Statin" if any(statin in row['Medications'] for statin in statins)
        else "Consider Statin" if row['eGFR'] < 60 or pd.isna(row['Medications'])
        else "Not on Statin"
    ),
    axis=1
)

# Recommended Medications
def recommended_medications(eGFR):
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

CKD_review['Recommended_Medications'] = CKD_review.apply(
    lambda row: check_recommendations(row['Medications'], recommended_medications(row['eGFR'])), 
    axis=1
)

# HbA1c Target
CKD_review['HbA1c_Target'] = CKD_review['HbA1c'].apply(
    lambda x: "Adjust Diabetes Management" if pd.notna(x) and x > 53 else "On Target" if pd.notna(x) else None
)

# Lifestyle Advice
def lifestyle_advice(ckd_stage):
    if ckd_stage in ["Stage 1", "Stage 2"]:
        return (
            "Encourage a balanced diet, including reduced sodium intake. "
            "Promote regular physical activity (150 minutes per week) as per general health guidance. "
            "Emphasize smoking cessation and maintaining a healthy weight."
        )
    elif ckd_stage in ["Stage 3a", "Stage 3b"]:
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

CKD_review['Lifestyle_Advice'] = CKD_review['CKD_Stage'].apply(lifestyle_advice)

# Dose Adjustment
def drug_adjustment(eGFR):
    adjustments = []
    with open(drug_adjustment_file, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if float(row['eGFR']) >= eGFR:
                adjustments.append(row['drug_adjustment'])
    return adjustments

def check_dose_adjustments(medications, adjustment_list):
    prescribed_adjustments = [drug for drug in adjustment_list if drug in medications]
    return ", ".join(prescribed_adjustments) if prescribed_adjustments else "No adjustments needed"

CKD_review['dose_adjustment_prescribed'] = CKD_review.apply(
    lambda row: check_dose_adjustments(row['Medications'], drug_adjustment(row['eGFR'])), 
    axis=1
)

# Anaemia Flag
CKD_review['Anaemia_Flag'] = CKD_review['haemoglobin'].apply(
    lambda x: "Consider ESA/Iron" if pd.notna(x) and x < 110 else "No Action Needed"
)

# Vitamin D Flag
CKD_review['Vitamin_D_Flag'] = CKD_review['Vitamin_D'].apply(
    lambda x: "Vitamin D Deficiency" if pd.notna(x) and x < 30 else "Normal"
)

# All Contraindications
def check_all_contraindications(medications, eGFR):
    contraindicated = get_contraindicated_drugs(eGFR)
    contraindicated_in_meds = [drug for drug in contraindicated if drug in medications]
    return ", ".join(contraindicated_in_meds) if contraindicated_in_meds else "No contraindications"

CKD_review['All_Contraindications'] = CKD_review.apply(
    lambda row: check_all_contraindications(row['Medications'], row['eGFR']), 
    axis=1
)

# Rename columns for clarity
CKD_review.rename(columns={
    'Date': 'Sample_Date', 'Date.1': 'Sample_Date1', 'Date.2': 'Sample_Date2', 'Date.3': 'Sample_Date3', 
    'Date.4': 'Sample_Date4', 'Date.5': 'Sample_Date5', 'Date.6': 'Sample_Date6', 
    'Date.7': 'Sample_Date7', 'Date.8': 'Sample_Date8', 'Date.9': 'Sample_Date9', 
    'Date.10': 'Sample_Date10', 'Date.11': 'Sample_Date11', 'HC Number': 'HC_Number'
}, inplace=True)

# Convert HC_Number to integer safely
CKD_review['HC_Number'] = pd.to_numeric(CKD_review['HC_Number'], errors='coerce').astype('Int64')

print("Data preprocessing and metrics calculation complete.")
print("Writing Output Data ...")

# Save output to CSV
output_file_name = f"eGFR_check_{pd.Timestamp.today().date()}.csv"
CKD_review.to_csv(output_file_name, index=False)

# Modify generate_patient_html to save HTML reports
def generate_patient_html(data, template_dir=current_dir, output_dir="Patient_Summaries_HTML"):
    # Format date columns to "YYYY-MM-DD" if present
    date_columns = [col for col in data.columns if "Date" in col]
    for date_col in date_columns:
        data[date_col] = pd.to_datetime(data[date_col], errors='coerce').dt.strftime("%Y-%m-%d")
    
    # Create the absolute path for output directory
    output_dir = os.path.abspath(output_dir)
    
    # Create date-stamped folder inside the output directory
    date_folder = os.path.join(output_dir, datetime.now().strftime("%Y-%m-%d"))
    os.makedirs(date_folder, exist_ok=True)
    
    # Set up Jinja2 environment to load HTML template
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("report_template.html")  # Template for patient summaries
    
    # Loop through each patient's data and generate HTML
    for _, patient in data.iterrows():
        # Print info message before generating report
        print(f"Generating HTML report for Patient HC_Number: {patient['HC_Number']}...")
        
        # Render the HTML content for each patient
        html_content = template.render(patient=patient)
        
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
def review_message(row):
    # Parse 'Sample_Date' to ensure it's in datetime format if not already
    eGFR_date = pd.to_datetime(row['Sample_Date'], errors='coerce').date() if pd.notna(row['Sample_Date']) else None

    # Convert CKD_ACR and risk_5yr to numeric values, setting errors='coerce' to handle non-numeric entries
    CKD_ACR = pd.to_numeric(row['CKD_ACR'], errors='coerce')
    risk_5yr = pd.to_numeric(row['risk_5yr'], errors='coerce')

    # Check if 'eGFR_date' is valid and calculate days since eGFR
    if eGFR_date:
        days_since_eGFR = (datetime.now().date() - eGFR_date).days
       # print(f"Patient HC_Number {row['HC_Number']} - eGFR Date: {eGFR_date}, Days since eGFR: {days_since_eGFR}")

        # NICE guideline checks based on CKD stage and ACR
        if row['CKD_Stage'] in ["Stage 1", "Stage 2"]:
            if days_since_eGFR > 365 or CKD_ACR > 3:
                return "Review Required (CKD Stage 1-2 with >1 year since last eGFR or ACR >3)"
            else:
                return "No immediate review required"
        elif row['CKD_Stage'] in ["Stage 3", "Stage 3a", "Stage 3b", "Stage 4", "Stage 5"]:
            if CKD_ACR > 30 or risk_5yr > 5 or days_since_eGFR > 180:
                return "Review Required (CKD Stage 3-5 with >6 months since last eGFR, ACR >30, or high-risk)"
            elif days_since_eGFR > 90:
                return "Review Required (CKD Stage 3-5 with >3 months since last eGFR)"
            else:
                return "No immediate review required"
        else:
            return "No CKD stage specified"
    else:
        # Handle case where 'Sample_Date' is missing or invalid
        return "Review Required (eGFR date unavailable)"

# Apply review message function to add 'review_message' column
data['review_message'] = data.apply(review_message, axis=1)

print("Generating reports...")

# Function to rename folders based on mapping
def rename_folders(date_folder):
    # Define mapping with simpler names
    folder_mapping = {
        "Review_Required__CKD_Stage_1_2_with__1_year_since_last_eGFR_or_ACR__3_": "Stage_1_2_Year_eGFR_or_ACR3",
        "No_immediate_review_required": "No_Immediate_Review",
        "Review_Required__CKD_Stage_3_5_with__6_months_since_last_eGFR__ACR__30__or_high_risk_": "Stage_3_5_6Months_eGFR_ACR30_HighRisk",
        "Review_Required__CKD_Stage_3_5_with__3_months_since_last_eGFR": "Stage_3_5_3Months_eGFR",
        "No_CKD_stage_specified": "No_CKD_Stage_Specified",
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

# Function to move both the eGFR file and CKD_review file to the date-stamped folder
def move_ckd_files(date_folder):
    # Construct file names based on today's date
    egfr_file = f"eGFR_check_{pd.Timestamp.today().date()}.csv"
    ckd_review_file = "CKD_review.csv"  # Static filename for CKD_review
    missing_KFRE_file = "missing_data_subjects.csv"

    # Construct source and destination paths for both files
    egfr_source = os.path.join(current_dir, egfr_file)
    egfr_destination = os.path.join(date_folder, egfr_file)
    
    ckd_source = os.path.join(current_dir, ckd_review_file)
    ckd_destination = os.path.join(date_folder, ckd_review_file)

    missing_source = os.path.join(current_dir, missing_KFRE_file)
    missing_destination = os.path.join(date_folder, missing_KFRE_file)

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

# Run the functions in sequence
date_folder = generate_patient_html(data)  # Generate PDFs and capture the returned date folder path
rename_folders(date_folder)               # Rename folders within the date-stamped directory
move_ckd_files(date_folder)  # Moves both eGFR and CKD_review files to the date-stamped folder
print("\nCKD Analysis and Reporting Completed ")
print(f"All reports and data saved in the folder: {date_folder}")
print("Please review missing file alerts above if applicable.\n")
