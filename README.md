The "NephroPath program" is a tool designed to streamline the process of creating Chronic Kidney Disease (CKD) staging reports for patients, utilizing data exported from the EMIS system used in UK healthcare settings.   
Here's a breakdown of the setup and usage:  

Key Features:  
Automated Reports: Creates patient-specific CKD staging reports based on EMIS data.
NICE Guidelines Compliance: Incorporates the latest NICE CKD guidelines for accurate staging.
Medication Recommendations: Provides drug adjustments and contraindicated medications based on kidney function.

Prerequisites  
NephroPath.exe: This executable handles report generation and comes with built-in dependencies.   
The code will download wkhtmltopdf. You will be asked to manually install this. (Project maintained to by Ashish Kulkarni, originally created by and credit to Jakob Truelsen.)

Required Files:  
report_template.html: HTML template for report formatting.  
contrindicated_drugs.csv: List of drugs contraindicated in CKD.  
drug_adjustment.csv: Guidelines for dosage adjustments based on CKD stage.  
Creatinine.csv: Grenerated using the XML file imported into the EMIS system.  
CKD_check.csv: Grenerated using the XML file imported into the EMIS system. 

Getting Started  
EMIS Data Export:
Log into EMIS and access the report/import functionality. Configure and import the provided EMIS XML files. (Please click here from step by step instructions https://www.emisnow.com/csm?id=kb_article&sys_id=a45d7aefc36cca10794e322d0501316a)
Export the EMIS data.
Save the Creatainine data as Creatinine.csv in the project directory.
Save the CKD coded data as CKD_check.csv in the project directory.

Setting Up:  
1) Download the repository to your Desktop from https://github.com/NKillough32/CKD-Review/archive/refs/heads/main.zip
2) Move the EMIS downloads Creatinine.csv, CKD_check.csv into the same directory e.g. /CKD-Review.  

Or clone the repository:  
1) bash  "C:\Windows\System32\bash.exe"
2) cd cd /mnt/c/Users/"Name"/Desktop/ Change "Name" to your profile or computer name
3) Copy code: git clone https://github.com/NKillough32/CKD-Review.git  
4) Move EMIS downloads Creatinine.csv, CKD_check.csv into the same directory e.g. /CKD-Review.

This program enables the review of patients with potential or confirmed Chronic Kidney Disease (CKD) within the EMIS system. It offers three analysis options:  
1) Patients with Two eGFR Results Below 90: Identifies individuals with at least two eGFR measurements under 90 mL/min/1.73m² alongside signs of kidney dysfunction, even if not formally coded as CKD.
2) Patients Coded as CKD: Focuses on reviewing those already coded with CKD within EMIS to ensure accurate monitoring and management.
3) Combined Analysis: Merges data from both groups, providing a comprehensive view of individuals with either a CKD diagnosis or lab evidence of kidney dysfunction.  
This approach enhances CKD case identification, supporting proactive management for both coded and potential cases, aligned with NICE guidance for optimal patient care.

Running the Report Generator:  
Execute NephroPath.exe, which will read the CSV files and create individualized CKD staging reports.

Output:  
For each patient, the generator will produce a report specifying their CKD stage, required interventions, and medication adjustments, if applicable.
This tool is an efficient resource for healthcare providers to manage CKD patients systematically, ensuring adherence to clinical guidelines and facilitating proactive patient care.
