import pandas as pd  # type: ignore
import os
import warnings
import sys
import logging
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
import qrcode
import pathlib
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)

# Get the current working directory
current_dir = os.getcwd()
output_dir = os.path.join(current_dir, "Patient_Summaries")  # Output directory for PDFs
surgery_info_file = os.path.join(current_dir, "Dependencies", "surgery_information.csv")

# Import the main CKD processing logic
from CKD_core import CKD_review  

# Function to load surgery information
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
        logging.warning(f"Surgery information file not found at {csv_path}")
        return {}
    except Exception as e:
        logging.error(f"Error reading surgery information: {str(e)}")
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
        
        logging.info(f"QR code generated successfully at: {output_path}")
        return output_path
    except Exception as e:
        logging.error(f"Error generating QR code: {e}")
        return None

# Function to generate patient PDF using ReportLab
def generate_patient_pdf(CKD_review, template_dir=os.path.join(current_dir, "Dependencies"), output_dir="Patient_Summaries"):
    # Load surgery info at start of function
    surgery_info = load_surgery_info()

    # Format date columns to "YYYY-MM-DD" if present
    date_columns = [col for col in CKD_review.columns if "Date" in col]
    for date_col in date_columns:
        CKD_review[date_col] = pd.to_datetime(CKD_review[date_col]).dt.strftime("%Y-%m-%d")
    
    # Generate CKD info QR code once
    qr_filename = "ckd_info_qr.png"
    qr_path = os.path.join(current_dir, "Dependencies", qr_filename)
    generate_ckd_info_qr(qr_path)
    
    # Print debug information
    logging.info(f"QR Code Path: {qr_path}")

    # Create the absolute path for output directory
    output_dir = os.path.abspath(output_dir)
    
    # Create date-stamped folder inside the output directory
    date_folder = os.path.join(output_dir, datetime.now().strftime("%Y-%m-%d"))
    os.makedirs(date_folder, exist_ok=True)

    # Replace empty cells with "Missing" in all columns
    columns_to_replace = CKD_review.columns  
    CKD_review[columns_to_replace] = CKD_review[columns_to_replace].replace({
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
        CKD_review[col] = CKD_review[col].apply(convert_to_numeric)

    # Function to create patient PDF using ReportLab
    def create_patient_pdf(patient, surgery_info, output_path, qr_path):
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()

        # Title
        title = Paragraph(f"{surgery_info.get('surgery_name', 'Unknown Surgery')} Chronic Kidney Disease Review", styles['Heading1'])
        elements.append(title)
        elements.append(Spacer(1, 12))

        # Review Status and EMIS Status
        review_status = f"Review Status: {patient['review_message'] if patient['review_message'] else 'Uncategorized'}"
        emis_status = f"Current EMIS Status: {patient['EMIS_CKD_Code']}"
        elements.append(Paragraph(review_status, styles['Normal']))
        elements.append(Paragraph(emis_status, styles['Normal']))
        elements.append(Spacer(1, 12))

        # Patient Information
        patient_info = [
            [Paragraph("Patient Information", styles['Heading3'])],
            [f"NHS Number: {int(patient['HC_Number']) if pd.notna(patient['HC_Number']) else 'N/A'}"],
            [f"Age: {int(patient['Age']) if pd.notna(patient['Age']) else 'N/A'} | Gender: {patient['Gender'] if patient['Gender'] else 'N/A'}"]
        ]
        table = Table(patient_info, colWidths=[500])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

        # CKD Overview (simplified based on HTML template)
        ckd_overview = [
            [Paragraph("CKD Overview", styles['Heading3'])],
            [f"Stage: {patient['CKD_Stage'] if patient['CKD_Stage'] else 'N/A'} | ACR Criteria: {patient['CKD_ACR'] if patient['CKD_ACR'] else 'N/A'}"],
            [f"Albumin-Creatinine Ratio (ACR): {patient['ACR'] if patient['ACR'] != 'Missing' else 'N/A'} mg/mmol | Date: {patient['Sample_Date1'] if patient['Sample_Date1'] else 'N/A'}"],
            [f"Creatinine (Current): {patient['Creatinine'] if patient['Creatinine'] != 'Missing' else 'N/A'} µmol/L | Date: {patient['Sample_Date'] if patient['Sample_Date'] else 'N/A'}"],
            [f"Creatinine (3 Months Prior): {patient['Creatinine_3m_prior'] if pd.notna(patient['Creatinine_3m_prior']) else 'N/A'} µmol/L | Date: {patient['Sample_Date2'] if patient['Sample_Date2'] else 'N/A'}"],
            [f"eGFR (Current): {patient['eGFR'] if patient['eGFR'] != 'Missing' else 'N/A'} ml/min/1.73m² | Date: {patient['Sample_Date'] if patient['Sample_Date'] else 'N/A'}"],
            [f"eGFR (3 Months Prior): {patient['eGFR_3m_prior'] if pd.notna(patient['eGFR_3m_prior']) else 'N/A'} ml/min/1.73m² | Date: {patient['Sample_Date2'] if patient['Sample_Date2'] else 'N/A'}"],
            [f"eGFR Trend: {patient['eGFR_Trend'] if patient['eGFR_Trend'] else 'N/A'}"]
        ]
        table = Table(ckd_overview, colWidths=[500])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

        # Blood Pressure (example of additional sections)
        bp_data = [
            [Paragraph("Blood Pressure", styles['Heading3'])],
            [f"Classification: {patient['BP_Classification'] if patient['BP_Classification'] != 'Missing' else 'N/A'} | Date: {patient['Sample_Date3'] if patient['Sample_Date3'] else 'N/A'}"],
            [f"Systolic / Diastolic: {patient['Systolic_BP'] if patient['Systolic_BP'] != 'Missing' else 'N/A'} / {patient['Diastolic_BP'] if patient['Diastolic_BP'] != 'Missing' else 'N/A'} mmHg"],
            [f"Target BP: {patient['BP_Target'] if patient['BP_Target'] != 'Missing' else 'N/A'} | Status: {patient['BP_Flag'] if patient['BP_Flag'] != 'Missing' else 'N/A'}"]
        ]
        table = Table(bp_data, colWidths=[500])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

        # Add more sections (Anaemia, Electrolytes, etc.) as needed, following the HTML template structure
        # For brevity, I’ll include only one more (Anaemia) as an example
        anaemia_data = [
            [Paragraph("Anaemia Overview", styles['Heading3'])],
            [f"Haemoglobin: {patient['haemoglobin'] if patient['haemoglobin'] != 'Missing' else 'N/A'} g/L | Date: {patient['Sample_Date5'] if patient['Sample_Date5'] else 'N/A'}"],
            [f"Current Status: {patient['Anaemia_Classification'] if patient['Anaemia_Classification'] != 'Missing' else 'N/A'}"],
            [f"Anaemia Management: {patient['Anaemia_Flag'] if patient['Anaemia_Flag'] else 'N/A'}"]
        ]
        table = Table(anaemia_data, colWidths=[500])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

        # QR Code and Surgery Info (simplified, as ReportLab doesn’t natively handle images easily)
        qr_text = "Scan QR code at https://patient.info/kidney-urinary-tract/chronic-kidney-disease-leaflet for more info."
        elements.append(Paragraph("More Information on Chronic Kidney Disease", styles['Heading2']))
        elements.append(Paragraph(qr_text, styles['Normal']))
        elements.append(Spacer(1, 12))

        # Surgery Contact Info
        surgery_contact = [
            [Paragraph("Surgery Contact Information", styles['Heading2'])],
            [f"{surgery_info.get('surgery_name', 'Unknown Surgery')}"],
            [f"{surgery_info.get('surgery_address_line1', 'N/A')}"],
            [f"{surgery_info.get('surgery_address_line2', 'N/A')}" if surgery_info.get('surgery_address_line2') else ""],
            [f"{surgery_info.get('surgery_city', 'N/A')}"],
            [f"{surgery_info.get('surgery_postcode', 'N/A')}"],
            [f"Tel: {surgery_info.get('surgery_phone', 'N/A')}"]
        ]
        table = Table(surgery_contact, colWidths=[500])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(table)

        # Build the PDF
        doc.build(elements)
        logging.info(f"PDF generated successfully at {output_path}")

    # Loop through each patient's data in CKD_review and generate PDF
    for _, patient in CKD_review.iterrows():
        # Merge surgery info into patient data
        patient_data = patient.to_dict()
        patient_data.update(surgery_info)  # Add surgery details to the patient's data

        # Sanitize review message for folder naming
        review_message = patient['review_message'] if patient['review_message'] else "Uncategorized"
        sanitized_review_folder = "".join([c if c.isalnum() or c.isspace() else "_" for c in review_message]).replace(" ", "_")
        
        # Create subfolder for the patient's review category
        review_folder = os.path.join(date_folder, sanitized_review_folder)
        os.makedirs(review_folder, exist_ok=True)
        
        # Generate PDF for this patient
        file_name = os.path.join(review_folder, f"Patient_Summary_{patient['HC_Number']}.pdf")
        create_patient_pdf(patient_data, surgery_info, file_name, qr_path)

        logging.info(f"Report saved as Patient_Summary_{patient['HC_Number']}.pdf in {review_folder}")

    # Return the date folder path for further use
    return date_folder

if __name__ == "__main__":
    # Assuming CKD_review is available from CKD_core
    try:
        # Run CKD_core to get CKD_review (you might need to load or process it differently)
        CKD_review = CKD_review  # This should be populated by CKD_core
        date_folder = generate_patient_pdf(CKD_review)
        logging.info(f"PDF generation completed. Files saved in: {date_folder}")
    except Exception as e:
        logging.error(f"Failed to generate PDFs: {e}")
        sys.exit(1)