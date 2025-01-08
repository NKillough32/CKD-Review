
# NephroPath Program

The NephroPath program is a tool designed to streamline the creation of Chronic Kidney Disease (CKD) staging reports for patients, using data exported from the EMIS system in UK healthcare settings.

## Key Features
- **Automated Reports:** Generates patient-specific CKD staging reports from EMIS data.
- **NICE Guidelines Compliance:** Aligns with the latest NICE CKD guidelines for accurate staging.
- **Medication Recommendations:** Includes drug adjustments and highlights contraindicated medications based on kidney function.

---

## Prerequisites
### 1. Executable File:
- **NephroPath.exe:** Handles report generation and includes built-in dependencies.
- **NephroPath_nopdf.exe:** Produces HTML files if third-party apps are not desired.

### 2. PDF Generation Dependency:
- The program will attempt to download `wkhtmltopdf`. A manual installation will be required.
- (Project maintained by Ashish Kulkarni, originally developed by Jakob Truelsen.)

### 3. Required Files:
- `report_template.html`: Formatting template for reports.
- `contraindicated_drugs.csv`: List of medications contraindicated in CKD.
- `drug_adjustment.csv`: Guidance for dosage adjustments based on CKD stage.
- `Creatinine.csv`: Generated from EMIS XML data present in a password protected zip file. 
- `CKD_check.csv`: Generated from EMIS XML data.

---

## Setup Instructions
### Option 1: Download the Repository
1. Download the repository as a ZIP file:  
   [https://github.com/NKillough32/CKD-Review/archive/refs/heads/main.zip](https://github.com/NKillough32/CKD-Review/archive/refs/heads/main.zip)
2. Extract the ZIP file to your Desktop.
3. Move the EMIS downloads (`Creatinine.csv`, `CKD_check.csv`) to the extracted directory (e.g., `/CKD-Review`).

### Option 2: Clone the Repository
1. Open Bash:  
   `"C:\Windows\System32\bash.exe"`
2. Navigate to your Desktop:  
   `cd /mnt/c/Users/"Name"/Desktop/`  
   Replace `"Name"` with your computer's profile name.
3. Clone the repository:  
   `git clone https://github.com/NKillough32/CKD-Review.git`

---

## Getting Started
### EMIS Data Export:
1. Log into EMIS and access the report/import functionality.
2. Import the provided EMIS XML files.  
   - Detailed step-by-step instructions: [EMIS XML Import Guide](https://www.emisnow.com/csm?id=kb_article&sys_id=a45d7aefc36cca10794e322d0501316a).
3. Export the EMIS data and save it in the project directory:
   - Save creatinine data as `Creatinine.csv`.
   - Save CKD-coded data as `CKD_check.csv`.

---

## Program Features
The program supports the review of patients with potential or confirmed CKD through three analysis options:
1. **Patients with Two eGFR Results Below 90:** Identifies individuals with at least two eGFR measurements under 90 mL/min/1.73m² alongside other signs of kidney dysfunction.
2. **Patients Coded as CKD:** Focuses on those already coded with CKD in EMIS to ensure accurate monitoring and management.
3. **Combined Analysis:** Provides a comprehensive overview of patients with either CKD diagnosis codes or lab evidence of kidney dysfunction.

This process aids in early identification and proactive management of CKD cases, adhering to NICE guidelines.

---

## Running the Report Generator
1. Execute `NephroPath.exe`.
2. The program will read the CSV files and generate individualized CKD staging reports.

---

## Output
Each report includes:
- CKD stage.
- Recommended interventions.
- Medication adjustments, if applicable.

This tool supports systematic CKD management, ensuring adherence to clinical guidelines while enabling efficient patient care.
