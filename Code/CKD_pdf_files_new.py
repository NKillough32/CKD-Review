import pandas as pd
import os
import warnings
import sys
import logging
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
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
    output_dir = os.path.join(os.getcwd(), "Patient_Summaries")
else:
    base_path = os.getcwd()
    output_dir = os.path.join(base_path, "Patient_Summaries")

surgery_info_file = os.path.join(base_path, "Dependencies", "surgery_information.csv")

# Function to load surgery information
def load_surgery_info(csv_path=surgery_info_file):
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

# Helper function to format value
def format_value(value, default="N/A"):
    return default if pd.isna(value) or value == "" or value == "Missing" else str(value)

# Helper function to classify status and return color
def classify_status(value, thresholds, field):
    if pd.isna(value) or value == "Missing":
        return colors.grey, "Missing"
    value = float(value) if isinstance(value, (int, float)) else value
    formatted_value = str(value)
    
    if field == "Creatinine":
        if value > 150:
            return colors.Color(0.69, 0, 0.125), formatted_value  # #B00020
        elif value >= 100:
            return colors.Color(0.827, 0.329, 0), formatted_value  # #D35400
        else:
            return colors.Color(0, 0.392, 0), formatted_value  # #006400
    elif field == "eGFR":
        if value < 30:
            return colors.Color(0.69, 0, 0.125), formatted_value  # #B00020
        elif value < 60:
            return colors.Color(0.827, 0.329, 0), formatted_value  # #D35400
        elif value < 90:
            return colors.Color(0, 0, 0.545), formatted_value  # #00008B
        else:
            return colors.Color(0, 0.392, 0), formatted_value  # #006400
    elif field == "Systolic_BP":
        if value >= 180:
            return colors.Color(0.69, 0, 0.125), formatted_value  # #B00020
        elif 140 <= value < 180:
            return colors.Color(0.827, 0.329, 0), formatted_value  # #D35400
        elif value < 90:
            return colors.Color(0, 0, 0.545), formatted_value  # #00008B
        else:
            return colors.Color(0, 0.392, 0), formatted_value  # #006400
    elif field == "Diastolic_BP":
        if value >= 120:
            return colors.Color(0.69, 0, 0.125), formatted_value  # #B00020
        elif 90 <= value < 120:
            return colors.Color(0.827, 0.329, 0), formatted_value  # #D35400
        elif value < 60:
            return colors.Color(0, 0, 0.545), formatted_value  # #00008B
        else:
            return colors.Color(0, 0.392, 0), formatted_value  # #006400
    elif field == "haemoglobin":
        if value < 80:
            return colors.Color(0.69, 0, 0.125), formatted_value  # #B00020
        elif 80 <= value <= 110:
            return colors.Color(0.827, 0.329, 0), formatted_value  # #D35400
        else:
            return colors.Color(0, 0.392, 0), formatted_value  # #006400
    elif field == "ACR":
        if value >= 30:
            return colors.Color(0.69, 0, 0.125), formatted_value  # #B00020
        elif value > 3:
            return colors.Color(0.827, 0.329, 0), formatted_value  # #D35400
        else:
            return colors.Color(0, 0.392, 0), formatted_value  # #006400
    elif field == "risk_2yr":
        if value >= 20:
            return colors.Color(0.69, 0, 0.125), formatted_value  # #B00020
        elif 10 <= value < 20:
            return colors.Color(0.827, 0.329, 0), formatted_value  # #D35400
        elif 1 <= value < 10:
            return colors.Color(0, 0, 0.545), formatted_value  # #00008B
        else:
            return colors.Color(0, 0.392, 0), formatted_value  # #006400
    elif field == "risk_5yr":
        if value >= 10:
            return colors.Color(0.69, 0, 0.125), formatted_value  # #B00020
        elif 5 <= value < 10:
            return colors.Color(0.827, 0.329, 0), formatted_value  # #D35400
        elif 1 <= value < 5:
            return colors.Color(0, 0, 0.545), formatted_value  # #00008B
        else:
            return colors.Color(0, 0.392, 0), formatted_value  # #006400
    elif field == "CKD_Group":
        if value in ['Normal Function', 'Stage 1 A1', 'Stage 2 A1']:
            return colors.Color(0, 0.392, 0), str(value)  # #006400 (safe)
        elif value in ['Stage 1 A2', 'Stage 2 A2', 'Stage 3A A1']:
            return colors.Color(0.722, 0.525, 0.043), str(value)  # #B8860B (warning)
        elif value in ['Stage 1 A3', 'Stage 2 A3', 'Stage 3A A2', 'Stage 3B A1', 'Stage 4 A1']:
            return colors.Color(0.827, 0.329, 0), str(value)  # #D35400 (caution)
        else:
            return colors.Color(0.69, 0, 0.125), str(value)  # #B00020 (critical)
    return colors.black, str(value)

# Function to compute review message based on clinical criteria
def compute_review_message(patient):
    eGFR = patient.get('eGFR')
    ACR = patient.get('ACR')
    risk_2yr = patient.get('risk_2yr')
    risk_5yr = patient.get('risk_5yr')
    ckd_stage = patient.get('CKD_Stage')
    
    # Convert to numeric where applicable
    try:
        eGFR = float(eGFR) if not pd.isna(eGFR) and eGFR != "Missing" else None
    except (ValueError, TypeError):
        eGFR = None
    try:
        ACR = float(ACR) if not pd.isna(ACR) and ACR != "Missing" else None
    except (ValueError, TypeError):
        ACR = None
    try:
        risk_2yr = float(risk_2yr) if not pd.isna(risk_2yr) and risk_2yr != "Missing" else None
    except (ValueError, TypeError):
        risk_2yr = None
    try:
        risk_5yr = float(risk_5yr) if not pd.isna(risk_5yr) and risk_5yr != "Missing" else None
    except (ValueError, TypeError):
        risk_5yr = None

    # Review criteria
    if ckd_stage in ["Stage 1", "Stage 2"]:
        if ACR is not None and ACR > 3:
            review_message = "Review Required - CKD Stage 1-2 with ACR > 3"
        elif eGFR is None or pd.isna(patient.get('Sample_Date')):
            review_message = "Review Required - eGFR date unavailable"
        else:
            review_message = "General Review - CKD Stage 1-2"
    elif ckd_stage in ["Stage 3A", "Stage 3B", "Stage 4", "Stage 5"]:
        if eGFR is not None and eGFR < 30:
            review_message = "Review Required - CKD Stage 3-5 with eGFR < 30"
        elif ACR is not None and ACR >= 30:
            review_message = "Review Required - CKD Stage 3-5 with ACR >= 30"
        elif risk_5yr is not None and risk_5yr > 5:
            review_message = "Review Required - CKD Stage 3-5 with 5-year risk > 5%"
        elif eGFR is None or pd.isna(patient.get('Sample_Date')):
            review_message = "Review Required - eGFR date unavailable"
        else:
            review_message = "General Review - CKD Stage 3-5"
    elif ckd_stage == "Normal Function":
        review_message = "No Immediate Review Required"
    else:
        review_message = "General Review - Unknown CKD Stage"
        logging.warning(f"Patient HC_Number: {patient.get('HC_Number')}, categorized as 'General Review - Unknown CKD Stage' due to CKD_Stage: {ckd_stage}, eGFR: {eGFR}, ACR: {ACR}, risk_5yr: {risk_5yr}")

    return review_message

# Function to map review_message to a shorter folder name
def map_review_message_to_folder(review_message):
    mapping = {
        "Review Required - CKD Stage 1-2 with ACR > 3": "Review_Stage1_2_ACR3",
        "Review Required - CKD Stage 3-5 with eGFR < 30": "Review_Stage3_5_eGFR30",
        "Review Required - CKD Stage 3-5 with ACR >= 30": "Review_Stage3_5_ACR30",
        "Review Required - CKD Stage 3-5 with 5-year risk > 5%": "Review_Stage3_5_Risk5",
        "Review Required - eGFR date unavailable": "Review_eGFR_Unavailable",
        "No Immediate Review Required": "No_Immediate_Review",
        "General Review - CKD Stage 1-2": "General_Review_Stage1_2",
        "General Review - CKD Stage 3-5": "General_Review_Stage3_5",
        "General Review - Unknown CKD Stage": "General_Review_Unknown"
    }
    return mapping.get(review_message, "".join([c if c.isalnum() or c.isspace() else "_" for c in review_message]).replace(" ", "_"))

# Function to compute CKD Group (same as in CKD_Master_pdf_exefree.py)
def get_ckd_stage_acr_group(row):
    eGFR = row.get('eGFR')
    ACR = row.get('ACR')

    # Debug logging to inspect input values
    logging.debug(f"Computing CKD_Group for eGFR: {eGFR}, ACR: {ACR}")

    if pd.isna(eGFR) or pd.isna(ACR):
        logging.debug("eGFR or ACR is NaN, returning 'No Data'")
        return "No Data"

    try:
        eGFR = float(eGFR)
        ACR = float(ACR)
    except (ValueError, TypeError) as e:
        logging.debug(f"Error converting eGFR or ACR to float: {e}, returning 'No Data'")
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
        logging.debug("eGFR out of expected range, returning 'No Data'")
        return "No Data"

# Function to create the stylesheet once with unique style names
def create_stylesheet():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='CustomTitle',
        fontName='Helvetica-Bold',  # Arial not typically available in ReportLab; Helvetica is close
        fontSize=32,
        leading=36,
        alignment=1,  # Center
        textColor=colors.black  # HTML uses black by default
    ))
    styles.add(ParagraphStyle(
        name='CustomSubTitle',
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        alignment=1,  # Center
        textColor=colors.black,
        spaceAfter=12
    ))
    styles.add(ParagraphStyle(
        name='CustomSectionHeader',
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=20,
        alignment=0,  # Left
        textColor=colors.black,
        spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        name='CustomNormalText',
        fontName='Helvetica',
        fontSize=12,  # Adjusted for better readability
        leading=14,
        spaceAfter=4,
        wordWrap='CJK'  # Enable better text wrapping
    ))
    styles.add(ParagraphStyle(
        name='CustomSmallText',
        fontName='Helvetica',
        fontSize=10,
        leading=12,
        spaceAfter=4,
        wordWrap='CJK'
    ))
    styles.add(ParagraphStyle(
        name='CustomTableTitle',
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        spaceAfter=4,
        wordWrap='CJK'
    ))
    styles.add(ParagraphStyle(
        name='CustomCenterText',
        fontName='Helvetica',
        fontSize=12,
        leading=14,
        alignment=1,  # Center
        spaceAfter=4
    ))
    return styles

# Function to generate patient PDF using ReportLab
def generate_patient_pdf(CKD_review, template_dir=None, output_dir=output_dir):
    # Load surgery info
    surgery_info = load_surgery_info()

    # Format date columns to "YYYY-MM-DD" if present
    date_columns = [col for col in CKD_review.columns if "Date" in col]
    for date_col in date_columns:
        CKD_review[date_col] = pd.to_datetime(CKD_review[date_col], errors='coerce').dt.strftime("%Y-%m-%d")
        # Log warning for malformed dates
        malformed_dates = CKD_review[date_col][CKD_review[date_col].isna() & CKD_review[date_col].notna()]
        if not malformed_dates.empty:
            logging.warning(f"Found {len(malformed_dates)} malformed entries in {date_col}: {malformed_dates.tolist()}")

    # Inspect CKD_review columns for debugging
    logging.info(f"CKD_review columns: {list(CKD_review.columns)}")
    
    # Check if CKD_Group is in the DataFrame
    if 'CKD_Group' not in CKD_review.columns:
        logging.warning("CKD_Group column not found in CKD_review, computing now...")
        CKD_review['CKD_Group'] = CKD_review.apply(get_ckd_stage_acr_group, axis=1)

    # Check if CKD_review is empty
    if CKD_review.empty:
        logging.warning("CKD_review DataFrame is empty. No PDFs will be generated.")
        date_folder = os.path.join(output_dir, datetime.now().strftime("%Y-%m-%d"))
        os.makedirs(date_folder, exist_ok=True)
        logging.info(f"Created empty patient summary folder: {date_folder}")
        return date_folder

    # Generate CKD info QR code once
    qr_filename = "ckd_info_qr.png"
    qr_path = os.path.join(base_path, "Dependencies", qr_filename)
    generate_ckd_info_qr(qr_path)
    
    logging.info(f"QR Code Path: {qr_path}")

    # Use provided output_dir
    date_folder = os.path.join(output_dir, datetime.now().strftime("%Y-%m-%d"))
    os.makedirs(date_folder, exist_ok=True)
    logging.info(f"Created patient summary folder: {date_folder}")

    # Replace empty cells with pd.NA in all columns
    CKD_review = CKD_review.replace({"": pd.NA, None: pd.NA, pd.NA: pd.NA, np.nan: pd.NA})

    # Convert numeric columns while preserving pd.NA
    numeric_columns = ['Phosphate', 'Calcium', 'Vitamin_D', 'Parathyroid', 'Bicarbonate', 'eGFR', 'Creatinine', 
                       'Systolic_BP', 'Diastolic_BP', 'haemoglobin', 'Potassium', 'HbA1c', 'risk_2yr', 'risk_5yr', 'ACR']
    for col in numeric_columns:
        if col in CKD_review.columns:
            CKD_review[col] = pd.to_numeric(CKD_review[col], errors='coerce')

    # Create the stylesheet once before generating PDFs
    styles = create_stylesheet()

    # Function to create patient PDF using ReportLab
    def create_patient_pdf(patient, surgery_info, output_path, qr_path, styles):
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            leftMargin=0.5*inch,
            rightMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch
        )
        elements = []

        # Compute review message dynamically
        patient['review_message'] = compute_review_message(patient)

        # Compute CKD_Group if missing
        if patient.get('CKD_Group', "Missing") == "Missing" or pd.isna(patient.get('CKD_Group')):
            patient['CKD_Group'] = get_ckd_stage_acr_group(patient)
        logging.info(f"Patient HC_Number: {patient['HC_Number']}, CKD_Group: {patient.get('CKD_Group')}, eGFR: {patient.get('eGFR')}, ACR: {patient.get('ACR')}")

        # Validate EMIS_CKD_Code vs. CKD_Stage
        if patient.get('EMIS_CKD_Code', '').lower().find('stage') != -1 and patient.get('CKD_Stage', '') != 'Unknown':
            emis_stage = patient['EMIS_CKD_Code'].lower()
            computed_stage = patient['CKD_Stage'].lower()
            if 'stage 3' in emis_stage and 'stage 3' not in computed_stage:
                logging.warning(f"Patient HC_Number: {patient['HC_Number']}, EMIS_CKD_Code '{patient['EMIS_CKD_Code']}' conflicts with computed CKD_Stage '{patient['CKD_Stage']}'")
            elif 'stage 2' in emis_stage and 'stage 2' not in computed_stage:
                logging.warning(f"Patient HC_Number: {patient['HC_Number']}, EMIS_CKD_Code '{patient['EMIS_CKD_Code']}' conflicts with computed CKD_Stage '{patient['CKD_Stage']}'")

        # Header
        header_table = Table([
            [Paragraph(f"{surgery_info.get('surgery_name', 'Unknown Surgery')}", styles['CustomTitle'])],
            [Paragraph("Chronic Kidney Disease Review", styles['CustomTitle'])],
        ], colWidths=[doc.width])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('BOTTOMPADDING', (0, 1), (-1, 1), 10),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 12))

        # Review Status and EMIS Status
        status_lines = [
            f"<b>Review Status:</b> {format_value(patient.get('review_message', 'Uncategorized'))}",
            f"<b>Current EMIS Status:</b> {format_value(patient.get('EMIS_CKD_Code'))}"
        ]
        if patient.get('Transplant_Kidney', 'Missing') != "Missing":
            status_lines.append(f"<b>Transplant:</b> {format_value(patient.get('Transplant_Kidney'))}")
        if patient.get('Dialysis', 'Missing') != "Missing":
            status_lines.append(f"<b>Dialysis:</b> {format_value(patient.get('Dialysis'))}")
        
        status_table = Table([[Paragraph(line, styles['CustomCenterText'])] for line in status_lines], colWidths=[doc.width])
        status_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(status_table)
        elements.append(Spacer(1, 20))

        # Results Overview
        elements.append(Paragraph("Results Overview", styles['CustomSubTitle']))
        elements.append(Spacer(1, 20))

        # Patient Information
        elements.append(Paragraph("Patient Information", styles['CustomSectionHeader']))
        patient_info_data = [
            [f"• <b>NHS Number:</b> {int(patient['HC_Number']) if pd.notna(patient['HC_Number']) else 'N/A'}"],
            [f"• <b>Age:</b> {int(patient['Age']) if pd.notna(patient['Age']) else 'N/A'} | <b>Gender:</b> {format_value(patient.get('Gender'))}"]
        ]
        patient_info_table = Table(patient_info_data, colWidths=[doc.width])
        patient_info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOX', (0, 0), (-1, -1), 2, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 15),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 14),
        ]))
        elements.append(patient_info_table)
        elements.append(Spacer(1, 20))

        # CKD Overview
        elements.append(Paragraph("CKD Overview", styles['CustomSectionHeader']))
        ckd_color, ckd_group = classify_status(patient.get('CKD_Group', 'Missing'), None, "CKD_Group")
        kdigo_table = Table([
            [Paragraph("<b>KDIGO 2024 Classification</b>", styles['CustomNormalText'])],
            [Paragraph(f"<font color='{ckd_color.hexval()}'>{ckd_group}</font>", styles['CustomNormalText'])]
        ], colWidths=[1.5*inch])
        kdigo_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 10),
        ]))
        
        ckd_data = [
            [f"• <b>Stage:</b> {format_value(patient.get('CKD_Stage'))} | <b>ACR Criteria:</b> {format_value(patient.get('CKD_ACR'))}"],
            [f"• <b>Albumin-Creatinine Ratio (ACR):</b> <font color='{classify_status(patient.get('ACR', 'Missing'), None, 'ACR')[0].hexval()}'>{format_value(patient.get('ACR'))} mg/mmol</font> | <b>Date:</b> {format_value(patient.get('Sample_Date1'))}"],
            [f"• <b>Creatinine:</b>"],
            [f"    - <b>Current:</b> <font color='{classify_status(patient.get('Creatinine', 'Missing'), None, 'Creatinine')[0].hexval()}'>{format_value(patient.get('Creatinine'))} µmol/L</font> | <b>Date:</b> {format_value(patient.get('Sample_Date'))}"],
            [f"    - <b>3 Months Prior:</b> {format_value(patient.get('Creatinine_3m_prior'))} µmol/L | <b>Date:</b> {format_value(patient.get('Sample_Date2'))}"],
            [f"• <b>eGFR:</b>"],
            [f"    - <b>Current:</b> <font color='{classify_status(patient.get('eGFR', 'Missing'), None, 'eGFR')[0].hexval()}'>{format_value(patient.get('eGFR'))} mL/min/1.73m²</font> | <b>Date:</b> {format_value(patient.get('Sample_Date'))}"],
            [f"    - <b>3 Months Prior:</b> {format_value(patient.get('eGFR_3m_prior'))} mL/min/1.73m² | <b>Date:</b> {format_value(patient.get('Sample_Date2'))}"],
            [f"    - <b>eGFR Trend:</b> {format_value(patient.get('eGFR_Trend'))}"]
        ]
        
        ckd_inner_table = Table(ckd_data, colWidths=[doc.width - 2*inch])
        ckd_inner_table.setStyle(TableStyle([
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 5),
            ('LEADING', (0, 0), (-1, -1), 14),
        ]))
        
        ckd_table = Table([
            ['', kdigo_table],
            [ckd_inner_table, '']
        ], colWidths=[doc.width - 2*inch, 2*inch])
        ckd_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('VALIGN', (1, 0), (1, 0), 'TOP'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('BOX', (0, 0), (-1, -1), 2, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 15),
        ]))
        elements.append(ckd_table)
        
        elements.append(Spacer(1, 5))
        elements.append(Paragraph(
            "<i>The eGFR trend is assessed by comparing the most recent value with the reading from three months prior. The change is adjusted to an annualized rate based on the time interval between measurements.</i>",
            styles['CustomSmallText']
        ))
        elements.append(Paragraph(
            "• <b>Rapid Decline:</b> A decrease of more than 5 mL/min/1.73m² per year or a relative drop of 25% or more.",
            styles['CustomSmallText']
        ))
        elements.append(Paragraph(
            "• <b>Stable:</b> No significant decline.",
            styles['CustomSmallText']
        ))
        elements.append(Paragraph(
            "A rapid decline may indicate progressive CKD, requiring closer monitoring or intervention.",
            styles['CustomSmallText']
        ))
        elements.append(Spacer(1, 20))

        # Blood Pressure
        elements.append(Paragraph("Blood Pressure", styles['CustomSectionHeader']))
        bp_color_sys, bp_value_sys = classify_status(patient.get('Systolic_BP', 'Missing'), None, 'Systolic_BP')
        bp_color_dia, bp_value_dia = classify_status(patient.get('Diastolic_BP', 'Missing'), None, 'Diastolic_BP')
        bp_data = [
            [f"• <b>Classification:</b> {format_value(patient.get('BP_Classification'))} | <b>Date:</b> {format_value(patient.get('Sample_Date3'))}"],
            [f"• <b>Systolic / Diastolic:</b> <font color='{bp_color_sys.hexval()}'>{bp_value_sys}</font> / <font color='{bp_color_dia.hexval()}'>{bp_value_dia}</font> mmHg"],
            [f"• <b>Target BP:</b> {format_value(patient.get('BP_Target'))} | <b>BP Status:</b> {format_value(patient.get('BP_Flag'))}"]
        ]
        bp_table = Table(bp_data, colWidths=[doc.width])
        bp_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOX', (0, 0), (-1, -1), 2, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 15),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 14),
        ]))
        elements.append(bp_table)
        elements.append(Spacer(1, 20))

        # Anaemia Overview
        elements.append(Paragraph("Anaemia Overview", styles['CustomSectionHeader']))
        haemoglobin_color, haemoglobin_value = classify_status(patient.get('haemoglobin', 'Missing'), None, 'haemoglobin')
        anaemia_data = [
            [f"• <b>Haemoglobin:</b> <font color='{haemoglobin_color.hexval()}'>{haemoglobin_value} g/L</font> | <b>Date:</b> {format_value(patient.get('Sample_Date5'))}"],
            [f"• <b>Current Status:</b> {format_value(patient.get('Anaemia_Classification'))}"],
            [f"• <b>Anaemia Management:</b> {format_value(patient.get('Anaemia_Flag'))}"]
        ]
        anaemia_table = Table(anaemia_data, colWidths=[doc.width])
        anaemia_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOX', (0, 0), (-1, -1), 2, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 15),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 14),
        ]))
        elements.append(anaemia_table)
        elements.append(Spacer(1, 20))

        # Electrolyte and MBD Management
        elements.append(Paragraph("Electrolyte and Mineral Bone Disorder (MBD) Management", styles['CustomSectionHeader']))
        # Deduplicate Vitamin D entries
        vitamin_d_entries = [(patient.get('Vitamin_D', 'Missing'), patient.get('Vitamin_D_Flag', 'Missing'), patient.get('Sample_Date10', 'Missing'))]
        seen_vitamin_d = set()
        unique_vitamin_d = []
        for value, flag, date in vitamin_d_entries:
            entry = (value, flag, date)
            if entry not in seen_vitamin_d:
                seen_vitamin_d.add(entry)
                unique_vitamin_d.append(entry)
            else:
                logging.warning(f"Patient HC_Number: {patient['HC_Number']}, duplicate Vitamin D entry: {value}, {flag}, {date}")

        mbd_data = [
            [f"• <b>Potassium:</b> <font color='{classify_status(patient.get('Potassium', 'Missing'), None, 'Potassium')[0].hexval()}'>{format_value(patient.get('Potassium'))} mmol/L</font> | <b>Status:</b> {format_value(patient.get('Potassium_Flag'))} | <b>Date:</b> {format_value(patient.get('Sample_Date7'))}"],
            [f"• <b>Bicarbonate:</b> <font color='{classify_status(patient.get('Bicarbonate', 'Missing'), None, 'Bicarbonate')[0].hexval()}'>{format_value(patient.get('Bicarbonate'))} mmol/L</font> | <b>Status:</b> {format_value(patient.get('Bicarbonate_Flag'))} | <b>Date:</b> {format_value(patient.get('Sample_Date13'))}"],
            [f"• <b>Parathyroid Hormone (PTH):</b> <font color='{classify_status(patient.get('Parathyroid', 'Missing'), None, 'Parathyroid')[0].hexval()}'>{format_value(patient.get('Parathyroid'))} pg/mL</font> | <b>Status:</b> {format_value(patient.get('Parathyroid_Flag'))} | <b>Date:</b> {format_value(patient.get('Sample_Date12'))}"],
            [f"• <b>Phosphate:</b> <font color='{classify_status(patient.get('Phosphate', 'Missing'), None, 'Phosphate')[0].hexval()}'>{format_value(patient.get('Phosphate'))} mmol/L</font> | <b>Status:</b> {format_value(patient.get('Phosphate_Flag'))} | <b>Date:</b> {format_value(patient.get('Sample_Date8'))}"],
            [f"• <b>Calcium:</b> <font color='{classify_status(patient.get('Calcium', 'Missing'), None, 'Calcium')[0].hexval()}'>{format_value(patient.get('Calcium'))} mmol/L</font> | <b>Status:</b> {format_value(patient.get('Calcium_Flag'))} | <b>Date:</b> {format_value(patient.get('Sample_Date9'))}"]
        ]
        for value, flag, date in unique_vitamin_d:
            mbd_data.append(
                [f"• <b>Vitamin D Level:</b> <font color='{classify_status(value, None, 'Vitamin_D')[0].hexval()}'>{format_value(value)} ng/mL</font> | <b>Status:</b> {format_value(flag)} | <b>Date:</b> {format_value(date)}"]
            )
        
        mbd_inner_table = Table(mbd_data, colWidths=[doc.width])
        mbd_inner_table.setStyle(TableStyle([
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 5),
            ('LEADING', (0, 0), (-1, -1), 14),
        ]))
        
        mbd_status_table = Table([
            [Paragraph("<b>MBD Status</b>", styles['CustomNormalText'])],
            [Paragraph(f"{format_value(patient.get('CKD_MBD_Flag'))}", styles['CustomNormalText'])]
        ], colWidths=[1.5*inch])
        mbd_status_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 10),
        ]))
        
        mbd_table = Table([
            [mbd_inner_table],
            [mbd_status_table]
        ], colWidths=[doc.width])
        mbd_table.setStyle(TableStyle([
            ('ALIGN', (0, 1), (-1, 1), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('BOX', (0, 0), (-1, -1), 2, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 15),
        ]))
        elements.append(mbd_table)
        elements.append(Spacer(1, 20))

        # Diabetes and HbA1c Management
        elements.append(Paragraph("Diabetes and HbA1c Management", styles['CustomSectionHeader']))
        hba1c_color, hba1c_value = classify_status(patient.get('HbA1c', 'Missing'), None, 'HbA1c')
        diabetes_data = [
            [f"• <b>HbA1c Level:</b> <font color='{hba1c_color.hexval()}'>{hba1c_value} mmol/mol</font> | <b>Date:</b> {format_value(patient.get('Sample_Date6'))}"],
            [f"• <b>HbA1c Management:</b> {format_value(patient.get('HbA1c_Target'))}"]
        ]
        diabetes_table = Table(diabetes_data, colWidths=[doc.width])
        diabetes_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOX', (0, 0), (-1, -1), 2, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 15),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 14),
        ]))
        elements.append(diabetes_table)
        elements.append(Spacer(1, 20))

        # Kidney Failure Risk
        elements.append(Paragraph("Kidney Failure Risk", styles['CustomSectionHeader']))
        risk_2yr_color, risk_2yr_value = classify_status(patient.get('risk_2yr', 'Missing'), None, 'risk_2yr')
        risk_5yr_color, risk_5yr_value = classify_status(patient.get('risk_5yr', 'Missing'), None, 'risk_5yr')
        risk_data = [
            [f"• <b>2-Year Risk:</b> <font color='{risk_2yr_color.hexval()}'>{risk_2yr_value}%</font>"],
            [f"• <b>5-Year Risk:</b> <font color='{risk_5yr_color.hexval()}'>{risk_5yr_value}%</font>"]
        ]
        risk_table = Table(risk_data, colWidths=[doc.width])
        risk_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOX', (0, 0), (-1, -1), 2, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 15),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 14),
        ]))
        elements.append(risk_table)
        elements.append(Spacer(1, 5))
        elements.append(Paragraph(
            "<i>The patient's 2- and 5-year kidney failure risk scores estimate the likelihood that their kidney disease will progress to kidney failure within the next 2 or 5 years. These scores are calculated based on the patient's current kidney function and other risk factors such as age, blood pressure, and existing health conditions. Understanding these risk scores helps in predicting disease progression and planning appropriate treatment strategies.</i>",
            styles['CustomSmallText']
        ))
        elements.append(Spacer(1, 20))

        # Care & Referrals
        elements.append(Paragraph("Care & Referrals", styles['CustomSectionHeader']))
        care_data = [
            [f"• <b>Multidisciplinary Care:</b> {format_value(patient.get('Multidisciplinary_Care'))}"],
            [f"• <b>Modality Education:</b> {format_value(patient.get('Modality_Education'))}"],
            [f"• <b>Nephrology Referral:</b> {format_value(patient.get('Nephrology_Referral'))}"],
            [f"• <b>Persistent Proteinuria:</b> {format_value(patient.get('Proteinuria_Flag'))}"]
        ]
        care_table = Table(care_data, colWidths=[doc.width])
        care_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOX', (0, 0), (-1, -1), 2, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 15),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 14),
        ]))
        elements.append(care_table)
        elements.append(Spacer(1, 20))

        # Medication Review
        elements.append(Paragraph("Medication Review", styles['CustomSectionHeader']))
        med_data = [
            [f"• <b>Current Medication:</b> {format_value(patient.get('Medications', 'None'))}"],
            [f"• <b>Review Medications:</b> {format_value(patient.get('dose_adjustment_prescribed'))}"],
            [f"• <b>Contraindicated Medications:</b> {format_value(patient.get('contraindicated_prescribed'))}"],
            [f"• <b>Suggested Medications:</b> {format_value(patient.get('Recommended_Medications', 'None'))}"],
            [f"• <b>Statin Recommendation:</b> {format_value(patient.get('Statin_Recommendation'))}"]
        ]
        med_table = Table(med_data, colWidths=[doc.width])
        med_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOX', (0, 0), (-1, -1), 2, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 15),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 14),
        ]))
        elements.append(med_table)
        elements.append(Spacer(1, 20))

        # Lifestyle and Preventative Advice
        elements.append(Paragraph("Lifestyle and Preventative Advice", styles['CustomSectionHeader']))
        lifestyle_data = [
            [f"• <b>Lifestyle Recommendations:</b> {format_value(patient.get('Lifestyle_Advice', 'No specific advice available.'))}"]
        ]
        lifestyle_table = Table(lifestyle_data, colWidths=[doc.width])
        lifestyle_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOX', (0, 0), (-1, -1), 2, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 15),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 14),
        ]))
        elements.append(lifestyle_table)
        elements.append(Spacer(1, 20))

        # NICE Guideline Recommendations
        elements.append(Paragraph("NICE Guideline Recommendations", styles['CustomSubTitle']))
        elements.append(Paragraph(
            "For detailed guidance, refer to <a href='https://www.nice.org.uk/guidance/ng203'>NICE NG203 guideline on Chronic Kidney Disease</a>.",
            styles['CustomNormalText']
        ))
        elements.append(Spacer(1, 10))

        ckd_stage = patient.get('CKD_Stage', 'Unknown')
        if ckd_stage == "Normal Function":
            nice_data = [
                ["<b>Recommendations for Normal Kidney Function</b>"],
                ["• <b>General Health Maintenance:</b> Encourage a balanced diet and regular physical activity. Avoid excessive use of NSAIDs and other nephrotoxic agents. Regular monitoring is not required unless risk factors are present."],
                ["• <b>Risk Factor Management:</b> Monitor blood pressure and maintain within normal ranges. Screen for diabetes and manage blood glucose levels if necessary."],
                ["• <b>Preventive Measures:</b> Encourage smoking cessation and limit alcohol intake. Stay hydrated and maintain a healthy weight."]
            ]
        elif ckd_stage == "Stage 1":
            nice_data = [
                ["<b>CKD Stage G1 Recommendations</b>"],
                ["• <b>Initial Assessment:</b> Perform Urine Albumin-to-Creatinine Ratio (ACR) testing to detect proteinuria, conduct haematuria screening, and monitor blood pressure (BP). Confirm stable renal function by reviewing prior estimated glomerular filtration rate (eGFR) results; if unavailable, re-evaluate renal function within 14 days."],
                ["• <b>Management and Monitoring:</b> Manage in primary care with annual monitoring if ACR is greater than 3 mg/mmol (indicative of microalbuminuria). If ACR is less than 3 mg/mmol, consider reducing the frequency of monitoring based on individual risk factors."],
                ["• <b>Lifestyle and Preventive Measures:</b> Encourage regular physical activity, smoking cessation, and maintaining a healthy weight. Aim for BP targets of less than 140/90 mmHg generally, or less than 130/80 mmHg if the patient has diabetes or an ACR greater than 70 mg/mmol (significant proteinuria)."],
                ["• <b>Medication:</b> Assess cardiovascular risk and consider initiating statin therapy if appropriate, following current guidelines."]
            ]
        elif ckd_stage == "Stage 2":
            nice_data = [
                ["<b>CKD Stage G2 Recommendations</b>"],
                ["• <b>Initial Assessment:</b> Repeat Urine ACR testing, haematuria screening, and BP monitoring as per Stage G1. Confirm stable renal function by reviewing previous eGFR results or retest within 14 days if necessary."],
                ["• <b>Management and Monitoring:</b> Continue primary care management with annual monitoring if ACR is greater than 3 mg/mmol. Reduce monitoring frequency if ACR is less than 3 mg/mmol and no additional risk factors are present."],
                ["• <b>Lifestyle and Preventive Measures:</b> Promote lifestyle interventions such as regular exercise, smoking cessation, and weight management. Maintain BP targets of less than 140/90 mmHg, or less than 130/80 mmHg for patients with diabetes or significant proteinuria (ACR >70 mg/mmol)."],
                ["• <b>Medication:</b> Evaluate cardiovascular risk and consider statin therapy as per guidelines. If proteinuria is present, consider initiating an ACE inhibitor or angiotensin receptor blocker (ARB) to reduce proteinuria and slow CKD progression."]
            ]
        elif ckd_stage == "Stage 3A":
            nice_data = [
                ["<b>CKD Stage G3a Recommendations</b>"],
                ["• <b>Monitoring and Risk Assessment:</b> Manage in primary care with at least annual renal function tests; increase monitoring to every 6 months if ACR is greater than 3 mg/mmol. Use the Kidney Failure Risk Equation (KFRE) at each assessment to estimate progression risk; refer to nephrology if the 5-year risk is greater than 5%."],
                ["• <b>Referral Criteria:</b> Refer to nephrology if ACR is greater than 70 mg/mmol, there’s a sustained decrease in eGFR of 25% or more over 12 months, or if significant proteinuria or haematuria is present."],
                ["• <b>Lifestyle and Preventive Measures:</b> Intensify cardiovascular risk management, including prescribing Atorvastatin 20 mg unless contraindicated. Maintain BP targets as per guidelines: less than 140/90 mmHg generally, or less than 130/80 mmHg if the patient has diabetes or significant proteinuria."],
                ["• <b>Medication:</b> Initiate or optimize ACE inhibitor or ARB therapy if proteinuria is present, unless contraindicated."],
                ["• <b>Patient Education:</b> Educate on CKD progression, importance of medication adherence, and regular monitoring."]
            ]
        elif ckd_stage == "Stage 3B":
            nice_data = [
                ["<b>CKD Stage G3b Recommendations</b>"],
                ["• <b>Monitoring and Risk Management:</b> Continue primary care management with renal function tests every 6 months, or more frequently if ACR is greater than 3 mg/mmol. Use the KFRE to assess progression risk; refer to nephrology if the 5-year risk exceeds 5% or if there’s a rapid decline in eGFR."],
                ["• <b>Referral Considerations:</b> Consider nephrology referral for further evaluation and management, especially if complications like anaemia, electrolyte imbalances, or bone mineral disorders arise."],
                ["• <b>Lifestyle and Preventive Measures:</b> Aggressively manage BP and cardiovascular risk factors. Optimize dosing of ACE inhibitors or ARBs. Continue statin therapy as indicated."],
                ["• <b>Patient Education:</b> Reinforce the importance of lifestyle modifications and adherence to treatment plans to slow CKD progression."]
            ]
        elif ckd_stage == "Stage 4":
            nice_data = [
                ["<b>CKD Stage G4 Recommendations</b>"],
                ["• <b>Specialist Management and Referral:</b> Routine referral to nephrology for co-management and preparation for potential renal replacement therapy. Regularly monitor eGFR, ACR, potassium, calcium, phosphate, and haemoglobin levels. Perform renal ultrasound if structural abnormalities or obstruction are suspected."],
                ["• <b>Management of Complications:</b> Monitor and manage anaemia, electrolyte imbalances, acidosis, and bone mineral disorders. Adjust medications that are renally excreted. Maintain BP targets as per guidelines."],
                ["• <b>Lifestyle and Preventive Measures:</b> Continue statin therapy (Atorvastatin 20 mg) for cardiovascular risk reduction. Provide vaccinations including influenza, pneumococcal, and COVID-19 as indicated. Regularly review medications to avoid nephrotoxic drugs and adjust dosages. Discontinue metformin if eGFR is less than 30 mL/min/1.73 m²."],
                ["• <b>Patient Education:</b> Discuss potential need for renal replacement therapy and available options. Provide guidance on diet, fluid intake, and symptom management."]
            ]
        elif ckd_stage == "Stage 5":
            nice_data = [
                ["<b>CKD Stage G5 Recommendations</b>"],
                ["• <b>Specialist Management and Comprehensive Care Plan:</b> Under specialist nephrology care with preparation for renal replacement therapy (dialysis or transplantation) as needed. Regularly monitor renal function and labs including electrolytes, bicarbonate, calcium, phosphate, haemoglobin, and fluid status."],
                ["• <b>Management of Complications:</b> Actively manage hyperkalaemia, metabolic acidosis, and anaemia (with iron supplementation and erythropoiesis-stimulating agents). Adjust or discontinue medications contraindicated in advanced CKD."],
                ["• <b>Lifestyle and Preventive Measures:</b> Continue statin therapy unless contraindicated. Provide comprehensive lifestyle guidance, including dietary advice (e.g., potassium and phosphate restrictions) and fluid management. Ensure all appropriate immunizations are up to date."],
                ["• <b>Patient Support and Education:</b> Offer psychological support and counseling. Educate the patient and family about end-stage renal disease management options and advance care planning."]
            ]
        else:
            nice_data = [
                ["<b>No specific recommendations available for this CKD stage.</b>"]
            ]

        nice_table = Table(nice_data, colWidths=[doc.width])
        nice_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOX', (0, 0), (-1, -1), 2, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 15),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 14),
        ]))
        elements.append(nice_table)
        elements.append(Spacer(1, 20))

        # Final Clinical Recommendations
        show_recommendations = (
            patient.get('review_message', '').startswith("Review Required") or
            patient.get('Nephrology_Referral') not in ["Not Indicated", "N/A", "Missing", None] or
            patient.get('dose_adjustment_prescribed') not in ["No adjustments needed", "N/A", "Missing", None] or
            patient.get('Statin_Recommendation') not in ["On Statin", "Not Indicated", "N/A", "Missing", None] or
            patient.get('Proteinuria_Flag') not in ["No Referral Needed", "N/A", "Missing", None] or
            patient.get('BP_Flag') not in ["On Target", "N/A", "Missing", None]
        )
        
        if show_recommendations:
            elements.append(Paragraph("Final Clinical Recommendations", styles['CustomSectionHeader']))
            final_recs = []
            if patient.get('review_message', '').startswith("Review Required"):
                final_recs.append([f"• <b>Renal Function Review Needed:</b> Yes"])
            recommendations = [
                ("Nephrology Referral", patient.get('Nephrology_Referral'), ["Not Indicated", "N/A", "Missing", None]),
                ("Medication Adjustments Required", patient.get('dose_adjustment_prescribed'), ["No adjustments needed", "N/A", "Missing", None]),
                ("Consider Statin Therapy", patient.get('Statin_Recommendation'), ["On Statin", "Not Indicated", "N/A", "Missing", None]),
                ("Consider Nephrology Referral", patient.get('Proteinuria_Flag'), ["No Referral Needed", "N/A", "Missing", None]),
                ("Blood Pressure Management", patient.get('BP_Target'), ["On Target", "N/A", "Missing", None])
            ]
            for title, value, ignore_list in recommendations:
                if value not in ignore_list:
                    # Escape special characters
                    safe_value = format_value(value).replace('<', '&lt;').replace('>', '&gt;')
                    final_recs.append([f"• <b>{title}:</b> {safe_value}"])
            final_recs_table = Table(final_recs, colWidths=[doc.width])
            final_recs_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 12),
                ('BOX', (0, 0), (-1, -1), 2, colors.grey),
                ('PADDING', (0, 0), (-1, -1), 15),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEADING', (0, 0), (-1, -1), 14),
            ]))
            elements.append(final_recs_table)
            elements.append(Spacer(1, 20))

        # QR Code and More Information
        elements.append(Paragraph("More Information on Chronic Kidney Disease", styles['CustomSubTitle']))
        qr_text = "Scan this QR code with your phone to access trusted resources on <b>Chronic Kidney Disease (CKD)</b>, including <br/>guidance on managing your condition, lifestyle recommendations, and when to seek medical advice."
        qr_section = Table([
            [Image(qr_path, width=150, height=150) if qr_path else Paragraph("QR code unavailable", styles['CustomNormalText'])],
            [Paragraph(qr_text, styles['CustomSmallText'])]
        ], colWidths=[doc.width])
        qr_section.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 10),
        ]))
        elements.append(qr_section)
        elements.append(Spacer(1, 20))

        # Surgery Contact Info
        surgery_contact_data = [
            [f"{surgery_info.get('surgery_name', 'Unknown Surgery')}"],
            [f"{surgery_info.get('surgery_address_line1', 'N/A')}"],
            [f"{surgery_info.get('surgery_address_line2', 'N/A')}" if surgery_info.get('surgery_address_line2') else ""],
            [f"{surgery_info.get('surgery_city', 'N/A')}"],
            [f"{surgery_info.get('surgery_postcode', 'N/A')}"],
            [f"<b>Tel:</b> {surgery_info.get('surgery_phone', 'N/A')}"]
        ]
        surgery_contact_table = Table(surgery_contact_data, colWidths=[doc.width])
        surgery_contact_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
        ]))
        elements.append(surgery_contact_table)
        elements.append(Spacer(1, 20))

        # Build the PDF with header and footer
        def add_header_footer(canvas, doc):
            canvas.saveState()
            canvas.setFont('Helvetica', 10)
            canvas.setFillColor(colors.black)
            canvas.drawString(doc.leftMargin, doc.pagesize[1] - doc.topMargin + 20, f"{surgery_info.get('surgery_name', 'Unknown Surgery')}")
            canvas.drawCentredString(doc.pagesize[0]/2, doc.pagesize[1] - doc.topMargin + 20, f"Chronic Kidney Disease Review")
            canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, doc.pagesize[1] - doc.topMargin + 20, f"Date: {datetime.now().strftime('%Y-%m-%d')}")
            canvas.line(doc.leftMargin, doc.pagesize[1] - doc.topMargin + 10, doc.pagesize[0] - doc.rightMargin, doc.pagesize[1] - doc.topMargin + 10)
            
            canvas.setFont('Helvetica', 8)
            canvas.setFillColor(colors.grey)
            canvas.drawString(doc.leftMargin, doc.bottomMargin - 10, f"Page {doc.page}")
            canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, doc.bottomMargin - 10, f"Tel: {surgery_info.get('surgery_phone', 'N/A')}")
            canvas.line(doc.leftMargin, doc.bottomMargin, doc.pagesize[0] - doc.rightMargin, doc.bottomMargin)
            canvas.restoreState()

        doc.build(elements, onFirstPage=add_header_footer, onLaterPages=add_header_footer)
        logging.info(f"PDF generated successfully at {output_path}")

    # Generate PDFs for each patient
    for _, patient in CKD_review.iterrows():
        patient_data = patient.to_dict()
        patient_data.update(surgery_info)

        # Compute review message before determining the folder
        review_message = compute_review_message(patient_data)
        patient_data['review_message'] = review_message

        # Compute CKD_Group if missing
        if patient_data.get('CKD_Group', "Missing") == "Missing" or pd.isna(patient_data.get('CKD_Group')):
            patient_data['CKD_Group'] = get_ckd_stage_acr_group(patient_data)
        logging.info(f"Patient HC_Number: {patient_data['HC_Number']}, CKD_Group: {patient_data.get('CKD_Group')}, eGFR: {patient_data.get('eGFR')}, ACR: {patient_data.get('ACR')}")

        # Create subfolder based on computed review_message with shortened name
        sanitized_review_folder = map_review_message_to_folder(review_message)
        review_folder = os.path.join(date_folder, sanitized_review_folder)
        os.makedirs(review_folder, exist_ok=True)
        logging.info(f"Created review subfolder: {review_folder}")
        
        file_name = os.path.join(review_folder, f"Patient_Summary_{patient['HC_Number']}.pdf")
        create_patient_pdf(patient_data, surgery_info, file_name, qr_path, styles)

        logging.info(f"Report saved as Patient_Summary_{patient['HC_Number']}.pdf in {review_folder}")

    return date_folder

# Main execution block to run the script
if __name__ == "__main__":
    try:
        input_file = os.path.join(base_path, "CKD_review.csv")
        CKD_review = pd.read_csv(input_file)
        output_folder = generate_patient_pdf(CKD_review)
        logging.info(f"All patient summaries generated in: {output_folder}")
    except FileNotFoundError:
        logging.error(f"Input file not found: {input_file}. Please ensure CKD_review.csv is generated by the pipeline.")
    except Exception as e:
        logging.error(f"Error during PDF generation: {str(e)}")