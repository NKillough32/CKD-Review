
# NephroPath Program

The NephroPath program is a tool designed to streamline the creation of Chronic Kidney Disease (CKD) staging reports for patients, using data exported from the EMIS system in UK healthcare settings.

## Key Features
- **Automated Reports:** Generates patient-specific CKD staging reports from EMIS data, including eGFR trends and risk assessments
- **NICE Guidelines Compliance:** Aligns with the latest NICE CKD guidelines for accurate staging and monitoring recommendations
- **Medication Management:** 
  - Provides drug dosage adjustment recommendations based on kidney function
  - Highlights contraindicated medications
  - Reviews statin requirements
- **Lifestyle Advice:** Generates stage-specific lifestyle and dietary recommendations
- **Risk Stratification:** Calculates 2-year and 5-year kidney failure risk scores for appropriate patients

---

## Prerequisites
### 1. Executable Files:
- **NephroPath.exe:** Full version with PDF report generation (Windows version)
- **NephroPath_mac:** Full version with PDF report generation (macOS version)
- **Alternative Versions**
    - **NephroPath.exe:** Full version with PDF report generation with wkhtmltopdf dependency (macOS version available)  
    - **NephroPath_html.exe:** Lightweight version that produces HTML reports only (macOS version available) 

### 2. PDF Generation (Full Version Only):
- PDF generation is now integrated into the application
- No external dependencies required
- Previous wkhtmltopdf requirement has been removed from the main program but is still a requirement of the Alternative version.
- (Project maintained by Ashish Kulkarni, originally developed by Jakob Truelsen.)

### 3. Required Data Files:
- Input Files (from EMIS):
  - `Creatinine.csv`: Patient laboratory data
  - `CKD_check.csv`: CKD diagnosis and coding data
- Program Files (included in repository):
  - `report_template.html`: Report formatting template
  - `contraindicated_drugs.csv`: Medication safety database
  - `drug_adjustment.csv`: Dosage adjustment guidelines

---

## Setup Instructions
### Option 1: Simple Setup (Recommended)
1. Download the latest release from:  
   [https://github.com/NKillough32/CKD-Review/releases](https://github.com/NKillough32/CKD-Review/releases)
2. Extract the ZIP file to a location of your choice
3. Copy your EMIS exports (`Creatinine.csv`, `CKD_check.csv`) to the `EMIS_Files` folder


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
   - Save creatinine data as `Creatinine.csv` to the EMIS_File folder overwriting the sample data.
   - Save CKD-coded data as `CKD_check.csv` to the EMIS_File folder overwriting the sample data.

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

## Output Format
### Individual Patient Reports
- Demographics
- Current CKD Stage (1-5)
- eGFR Trend Graph
- Risk Stratification
- Clinical Recommendations
  - Monitoring frequency
  - Medication adjustments
  - Specialist referral criteria
- Batch files for group data updating [EMIS Batch loading Guide](https://support.primarycareit.co.uk/portal/en-gb/kb/articles/how-to-bulk-code-p#Introduction)

### Practice-Level Summary
- Patient distribution by CKD stage
- Monitoring compliance rates
- Intervention priorities

This tool supports systematic CKD management, ensuring adherence to clinical guidelines while enabling efficient patient care.
