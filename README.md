The "CKD Staging Report Generator" is a tool designed to streamline the process of creating Chronic Kidney Disease (CKD) staging reports for patients, utilizing data exported from the EMIS system used in UK healthcare settings. Here's a breakdown of the setup and usage:

Key Features
Automated Reports: Creates patient-specific CKD staging reports based on EMIS data.
NICE Guidelines Compliance: Incorporates the latest NICE CKD guidelines for accurate staging.
Medication Recommendations: Provides drug adjustments and contraindicated medications based on kidney function.

Prerequisites
NephroPath.exe: This executable handles report generation and comes with built-in dependencies.

Required Files:
report_template.html: HTML template for report formatting.
contrindicated_drugs.csv: List of drugs contraindicated in CKD.
drug_adjustment.csv: Guidelines for dosage adjustments based on CKD stage.

Getting Started
EMIS Data Export:
Log into EMIS and access the report/export functionality.
Configure and export the patient data following CKD-specific criteria.
Save the data as Creatinine.csv in the project directory.

Setting Up:
Clone the repository:
bash
Copy code
git clone https://github.com/NKillough32/CKD-Review.git
Ensure Creatinine.csv and the template files are in the same directory.
Running the Report Generator:

Execute NephroPath.exe, which will read the CSV file and create individualized CKD staging reports.
Output
For each patient, the generator will produce a report specifying their CKD stage, required interventions, and medication adjustments, if applicable.
This tool is an efficient resource for healthcare providers to manage CKD patients systematically, ensuring adherence to clinical guidelines and facilitating proactive patient care.
