import pandas as pd
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
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)

# Get the base path
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.getcwd()

output_dir = os.path.join(base_path, "Patient_Summaries")
surgery_info_file = os.path.join(base_path, "Dependencies", "surgery_information.csv")

# Function to load surgery information
def load_surgery_info(csv_path=surgery_info_file):
    """Load surgery information from CSV file. Returns dictionary with surgery details."""
    try:
        surgery_df = pd.read_csv(csv_path)
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
    """Generate QR code linking to CKD patient information."""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data("https://patient.info/kidney-urinary-tract/chronic-kidney-disease-leaflet")
        qr.make(fit=True)
        qr_image = qr.make_image(fill_color="black", back_color="white")
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        qr_image.save(output_path, format='PNG')
        
        logging.info(f"QR code generated successfully at: {output_path}")
        return output_path
    except Exception as e:
        logging.error(f"Error generating QR code: {e}")
        return None

# Function to generate patient PDF using ReportLab
def generate_patient_pdf(CKD_review, template_dir=None, output_dir=output_dir):
    # Load surgery info
    surgery_info = load_surgery_info()

    # Format date columns to "YYYY-MM-DD" if present
    date_columns = [col for col in CKD_review.columns if "Date" in col]
    for date_col in date_columns:
        CKD_review[date_col] = pd.to_datetime(CKD_review[date_col], errors='coerce').dt.strftime("%Y-%m-%d")
    
    # Generate CKD info QR code once
    qr_filename = "ckd_info_qr.png"
    qr_path = os.path.join(base_path, "Dependencies", qr_filename)
    generate_ckd_info_qr(qr_path)
    
    logging.info(f"QR Code Path: {qr_path}")

    # Use provided output_dir (absolute path handled by caller if needed)
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
        review_status = f"Review Status: {patient['review_message'] if patient.get('review_message') else 'Uncategorized'}"
        emis_status = f"Current EMIS Status: {patient['EMIS_CKD_Code']}"
        elements.append(Paragraph(review_status, styles['Normal']))
        elements.append(Paragraph(emis_status, styles['Normal']))
        elements.append(Spacer(1, 12))

        # Patient Information
        patient_info = [
            [Paragraph("Patient Information", styles['Heading3'])],
            [f"NHS Number: {int(patient['HC_Number']) if pd.notna(patient['HC_Number']) else 'N/A'}"],
            [f"Age: {int(patient['Age']) if pd.notna(patient['Age']) else 'N/A'} | Gender: {patient['Gender'] if patient.get('Gender') else 'N/A'}"]
        ]
        table = Table(patient_info, colWidths=[500])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

        # CKD Overview
        ckd_overview = [
            [Paragraph("CKD Overview", styles['Heading3'])],
            [f"Stage: {patient['CKD_Stage'] if patient.get('CKD_Stage') else 'N/A'} | ACR Criteria: {patient['CKD_ACR'] if patient.get('CKD_ACR') else 'N/A'}"],
            [f"Albumin-Creatinine Ratio (ACR): {patient['ACR'] if patient.get('ACR') != 'Missing' else 'N/A'} mg/mmol | Date: {patient['Sample_Date1'] if patient.get('Sample_Date1') else 'N/A'}"],
            [f"Creatinine (Current): {patient['Creatinine'] if patient.get('Creatinine') != 'Missing' else 'N/A'} µmol/L | Date: {patient['Sample_Date'] if patient.get('Sample_Date') else 'N/A'}"],
            [f"Creatinine (3 Months Prior): {patient['Creatinine_3m_prior'] if pd.notna(patient.get('Creatinine_3m_prior')) else 'N/A'} µmol/L | Date: {patient['Sample_Date2'] if patient.get('Sample_Date2') else 'N/A'}"],
            [f"eGFR (Current): {patient['eGFR'] if patient.get('eGFR') != 'Missing' else 'N/A'} ml/min/1.73m² | Date: {patient['Sample_Date'] if patient.get('Sample_Date') else 'N/A'}"],
            [f"eGFR (3 Months Prior): {patient['eGFR_3m_prior'] if pd.notna(patient.get('eGFR_3m_prior')) else 'N/A'} ml/min/1.73m² | Date: {patient['Sample_Date2'] if patient.get('Sample_Date2') else 'N/A'}"],
            [f"eGFR Trend: {patient['eGFR_Trend'] if patient.get('eGFR_Trend') else 'N/A'}"]
        ]
        table = Table(ckd_overview, colWidths=[500])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

        # Blood Pressure
        bp_data = [
            [Paragraph("Blood Pressure", styles['Heading3'])],
            [f"Classification: {patient['BP_Classification'] if patient.get('BP_Classification') != 'Missing' else 'N/A'} | Date: {patient['Sample_Date3'] if patient.get('Sample_Date3') else 'N/A'}"],
            [f"Systolic / Diastolic: {patient['Systolic_BP'] if patient.get('Systolic_BP') != 'Missing' else 'N/A'} / {patient['Diastolic_BP'] if patient.get('Diastolic_BP') != 'Missing' else 'N/A'} mmHg"],
            [f"Target BP: {patient['BP_Target'] if patient.get('BP_Target') != 'Missing' else 'N/A'} | Status: {patient['BP_Flag'] if patient.get('BP_Flag') != 'Missing' else 'N/A'}"]
        ]
        table = Table(bp_data, colWidths=[500])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

        # Anaemia Overview
        anaemia_data = [
            [Paragraph("Anaemia Overview", styles['Heading3'])],
            [f"Haemoglobin: {patient['haemoglobin'] if patient.get('haemoglobin') != 'Missing' else 'N/A'} g/L | Date: {patient['Sample_Date5'] if patient.get('Sample_Date5') else 'N/A'}"],
            [f"Current Status: {patient['Anaemia_Classification'] if patient.get('Anaemia_Classification') != 'Missing' else 'N/A'}"],
            [f"Anaemia Management: {patient['Anaemia_Flag'] if patient.get('Anaemia_Flag') else 'N/A'}"]
        ]
        table = Table(anaemia_data, colWidths=[500])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

        # QR Code and Surgery Info
        qr_text = "Scan QR code at https://patient.info/kidney-urinary-tract/chronic-kidney-disease-leaflet for more info."
        elements.append(Paragraph("More Information on Chronic Kidney Disease", styles['Heading2']))
        elements.append(Paragraph(qr_text, styles['Normal']))
        elements.append(Spacer(1, 12))

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

        doc.build(elements)
        logging.info(f"PDF generated successfully at {output_path}")

    # Generate PDFs for each patient
    for _, patient in CKD_review.iterrows():
        patient_data = patient.to_dict()
        patient_data.update(surgery_info)

        review_message = patient.get('review_message', "Uncategorized")
        sanitized_review_folder = "".join([c if c.isalnum() or c.isspace() else "_" for c in review_message]).replace(" ", "_")
        
        review_folder = os.path.join(date_folder, sanitized_review_folder)
        os.makedirs(review_folder, exist_ok=True)
        
        file_name = os.path.join(review_folder, f"Patient_Summary_{patient['HC_Number']}.pdf")
        create_patient_pdf(patient_data, surgery_info, file_name, qr_path)

        logging.info(f"Report saved as Patient_Summary_{patient['HC_Number']}.pdf in {review_folder}")

    return date_folder