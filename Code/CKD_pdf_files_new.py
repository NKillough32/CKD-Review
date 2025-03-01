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
from html import escape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

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
    if pd.isna(value) or value == "" or value == "Missing":
        return default
    formatted = str(value)
    if formatted.startswith("N/"):
        return "N/A"
    return formatted

# Helper function to classify status and return color
def classify_status(value, thresholds, field):
    if pd.isna(value) or value == "Missing":
        return colors.grey, "Missing"
    value = float(value) if isinstance(value, (int, float)) else value
    formatted_value = str(value)
    
    if field == "Creatinine":
        if value > 150: return colors.Color(0.69, 0, 0.125), formatted_value  # #B00020
        elif value >= 100: return colors.Color(0.827, 0.329, 0), formatted_value  # #D35400
        else: return colors.Color(0, 0.392, 0), formatted_value  # #006400
    elif field == "eGFR":
        if value < 30: return colors.Color(0.69, 0, 0.125), formatted_value  # #B00020
        elif value < 60: return colors.Color(0.827, 0.329, 0), formatted_value  # #D35400
        elif value < 90: return colors.Color(0, 0, 0.545), formatted_value  # #00008B
        else: return colors.Color(0, 0.392, 0), formatted_value  # #006400
    elif field == "Systolic_BP":
        if value >= 180: return colors.Color(0.69, 0, 0.125), formatted_value  # #B00020
        elif 140 <= value < 180: return colors.Color(0.827, 0.329, 0), formatted_value  # #D35400
        elif value < 90: return colors.Color(0, 0, 0.545), formatted_value  # #00008B
        else: return colors.Color(0, 0.392, 0), formatted_value  # #006400
    elif field == "Diastolic_BP":
        if value >= 120: return colors.Color(0.69, 0, 0.125), formatted_value  # #B00020
        elif 90 <= value < 120: return colors.Color(0.827, 0.329, 0), formatted_value  # #D35400
        elif value < 60: return colors.Color(0, 0, 0.545), formatted_value  # #00008B
        else: return colors.Color(0, 0.392, 0), formatted_value  # #006400
    elif field == "haemoglobin":
        if value < 80: return colors.Color(0.69, 0, 0.125), formatted_value  # #B00020
        elif 80 <= value <= 110: return colors.Color(0.827, 0.329, 0), formatted_value  # #D35400
        else: return colors.Color(0, 0.392, 0), formatted_value  # #006400
    elif field == "ACR":
        if value >= 30: return colors.Color(0.69, 0, 0.125), formatted_value  # #B00020
        elif value > 3: return colors.Color(0.827, 0.329, 0), formatted_value  # #D35400
        else: return colors.Color(0, 0.392, 0), formatted_value  # #006400
    elif field == "risk_2yr":
        if value >= 20: return colors.Color(0.69, 0, 0.125), formatted_value  # #B00020
        elif 10 <= value < 20: return colors.Color(0.827, 0.329, 0), formatted_value  # #D35400
        elif 1 <= value < 10: return colors.Color(0, 0, 0.545), formatted_value  # #00008B
        else: return colors.Color(0, 0.392, 0), formatted_value  # #006400
    elif field == "risk_5yr":
        if value >= 10: return colors.Color(0.69, 0, 0.125), formatted_value  # #B00020
        elif 5 <= value < 10: return colors.Color(0.827, 0.329, 0), formatted_value  # #D35400
        elif 1 <= value < 5: return colors.Color(0, 0, 0.545), formatted_value  # #00008B
        else: return colors.Color(0, 0.392, 0), formatted_value  # #006400
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

# Function to compute CKD Group
def get_ckd_stage_acr_group(row):
    eGFR = row.get('eGFR')
    ACR = row.get('ACR')

    logging.debug(f"Computing CKD_Group for eGFR: {eGFR}, ACR: {ACR}")

    if pd.isna(eGFR) or pd.isna(ACR):
        logging.debug("eGFR or ACR is NaN, returning 'No Data'")
        return "No Data"

    try:
        eGFR = float(eGFR)
        ACR = float(ACR)
        if eGFR <= 0:
            logging.warning(f"Invalid eGFR value {eGFR} for HC_Number {row.get('HC_Number')}, expected positive value")
            return "No Data"
        if ACR < 0 or ACR > 1000:
            logging.warning(f"Invalid ACR value {ACR} for HC_Number {row.get('HC_Number')}, expected value between 0 and 1000")
            return "No Data"
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

# Function to create the stylesheet with adjusted styles to match HTML
def create_stylesheet():
    styles = getSampleStyleSheet()
    
    # Register Arial font
    try:
        pdfmetrics.registerFont(TTFont('Arial', os.path.join(base_path, "Dependencies", 'Arial.ttf')))
        font_name = 'Arial'
    except Exception as e:
        logging.warning(f"Failed to load Arial font from Dependencies folder: {str(e)}. Falling back to Helvetica.")
        font_name = 'Helvetica'

    # Register Arial-Bold font
    try:
        pdfmetrics.registerFont(TTFont('Arial-Bold', os.path.join(base_path, "Dependencies", 'arialbd.ttf')))
        font_name_bold = 'Arial-Bold'
    except Exception as e:
        logging.warning(f"Failed to load Arial-Bold font from Dependencies folder: {str(e)}. Falling back to Helvetica-Bold.")
        font_name_bold = 'Helvetica-Bold'

    logging.info(f"Using fonts - Regular: {font_name}, Bold: {font_name_bold}")

    styles.add(ParagraphStyle(
        name='CustomTitle',
        fontName=font_name_bold,
        fontSize=20,  # Matches script's h1
        leading=24,
        alignment=1,  # Center
        textColor=colors.black
    ))
    styles.add(ParagraphStyle(
        name='CustomSubTitle',
        fontName=font_name_bold,
        fontSize=16,  # Matches script's h2
        leading=18,
        alignment=1,  # Center
        textColor=colors.black,
        spaceAfter=12
    ))
    styles.add(ParagraphStyle(
        name='CustomSectionHeader',
        fontName=font_name_bold,
        fontSize=14,  # Matches script's h3
        leading=16,
        alignment=0,  # Left
        textColor=colors.black,
        spaceAfter=8
    ))
    styles.add(ParagraphStyle(
        name='CustomNormalText',
        fontName=font_name,
        fontSize=10,  # Matches HTML body text (~14px ≈ 10.5pt)
        leading=12,
        spaceAfter=4,
        wordWrap='CJK'
    ))
    styles.add(ParagraphStyle(
        name='CustomSmallText',
        fontName=font_name,
        fontSize=9,  # Matches HTML smaller text (~12px ≈ 9pt)
        leading=11,
        spaceAfter=4,
        wordWrap='CJK'
    ))
    styles.add(ParagraphStyle(
        name='CustomLongText',
        fontName=font_name,
        fontSize=9,
        leading=11,
        spaceAfter=4,
        wordWrap='CJK'
    ))
    styles.add(ParagraphStyle(
        name='CustomTableText',
        fontName=font_name,
        fontSize=10,
        leading=12,
        spaceAfter=4,
        wordWrap='CJK',
        allowWidows=1,
        alignment=0
    ))
    styles.add(ParagraphStyle(
        name='CustomTableTitle',
        fontName=font_name_bold,
        fontSize=10,
        leading=12,
        spaceAfter=4,
        wordWrap='CJK'
    ))
    styles.add(ParagraphStyle(
        name='CustomCenterText',
        fontName=font_name,
        fontSize=10,
        leading=12,
        alignment=1,  # Center
        spaceAfter=4
    ))
    return styles, font_name, font_name_bold

# Function to generate patient PDF using ReportLab
def generate_patient_pdf(CKD_review, template_dir=None, output_dir=output_dir):
    surgery_info = load_surgery_info()

    date_columns = [col for col in CKD_review.columns if "Date" in col]
    for date_col in date_columns:
        CKD_review[date_col] = pd.to_datetime(CKD_review[date_col], errors='coerce').dt.strftime("%Y-%m-%d")
        CKD_review[date_col] = CKD_review[date_col].apply(lambda x: "N/A" if pd.isna(x) or len(str(x)) < 10 else x)
        malformed_dates = CKD_review[date_col][CKD_review[date_col] == "N/A"]
        if not malformed_dates.empty:
            logging.warning(f"Found {len(malformed_dates)} malformed entries in {date_col}")

    logging.info(f"CKD_review columns: {list(CKD_review.columns)}")
    
    if 'CKD_Group' not in CKD_review.columns:
        logging.warning("CKD_Group column not found in CKD_review, computing now...")
        CKD_review['CKD_Group'] = CKD_review.apply(get_ckd_stage_acr_group, axis=1)

    if CKD_review.empty:
        logging.warning("CKD_review DataFrame is empty. No PDFs will be generated.")
        date_folder = os.path.join(output_dir, datetime.now().strftime("%Y-%m-%d"))
        os.makedirs(date_folder, exist_ok=True)
        logging.info(f"Created empty patient summary folder: {date_folder}")
        return date_folder

    qr_filename = "ckd_info_qr.png"
    qr_path = os.path.join(base_path, "Dependencies", qr_filename)
    generate_ckd_info_qr(qr_path)
    
    logging.info(f"QR Code Path: {qr_path}")

    date_folder = os.path.join(output_dir, datetime.now().strftime("%Y-%m-%d"))
    os.makedirs(date_folder, exist_ok=True)
    logging.info(f"Created patient summary folder: {date_folder}")

    CKD_review = CKD_review.replace({"": pd.NA, None: pd.NA, pd.NA: pd.NA, np.nan: pd.NA})

    numeric_columns = ['Phosphate', 'Calcium', 'Vitamin_D', 'Parathyroid', 'Bicarbonate', 'eGFR', 'Creatinine', 
                       'Systolic_BP', 'Diastolic_BP', 'haemoglobin', 'Potassium', 'HbA1c', 'risk_2yr', 'risk_5yr', 'ACR']
    for col in numeric_columns:
        if col in CKD_review.columns:
            CKD_review[col] = pd.to_numeric(CKD_review[col], errors='coerce')

    styles, font_name, font_name_bold = create_stylesheet()

    def create_patient_pdf(patient, surgery_info, output_path, qr_path, styles, font_name, font_name_bold):
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            leftMargin=0.5*inch,
            rightMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch
        )
        elements = []

        patient['review_message'] = compute_review_message(patient)

        if patient.get('CKD_Group', "Missing") == "Missing" or pd.isna(patient.get('CKD_Group')):
            patient['CKD_Group'] = get_ckd_stage_acr_group(patient)
        logging.info(f"Patient HC_Number: {patient['HC_Number']}, CKD_Group: {patient.get('CKD_Group')}, eGFR: {patient.get('eGFR')}, ACR: {patient.get('ACR')}")

        emis_code = patient.get('EMIS_CKD_Code', '')
        if emis_code is None:
            logging.warning(f"Patient HC_Number: {patient['HC_Number']}, EMIS_CKD_Code is None")
            emis_code = ''
        ckd_stage = patient.get('CKD_Stage', '')
        if emis_code.lower().find('stage') != -1 and ckd_stage != 'Unknown':
            if 'stage 3' in emis_code.lower() and 'stage 3' not in ckd_stage.lower():
                logging.warning(f"Patient HC_Number: {patient['HC_Number']}, EMIS_CKD_Code '{emis_code}' conflicts with computed CKD_Stage '{ckd_stage}'")
            elif 'stage 2' in emis_code.lower() and 'stage 2' not in ckd_stage.lower():
                logging.warning(f"Patient HC_Number: {patient['HC_Number']}, EMIS_CKD_Code '{emis_code}' conflicts with computed CKD_Stage '{ckd_stage}'")

        # Header
        header_table = Table([
            [Paragraph(f"{surgery_info.get('surgery_name', 'Unknown Surgery')}<br/>Chronic Kidney Disease Review", styles['CustomTitle'])],
        ], colWidths=[doc.width])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 0.3*inch))

        # Review Status and EMIS Status
        status_lines = [
            f"<b>Review Status:</b> {escape(format_value(patient.get('review_message', 'Uncategorized')))}",
            f"<b>Current EMIS Status:</b> {escape(format_value(patient.get('EMIS_CKD_Code')))}"
        ]
        if patient.get('Transplant_Kidney', 'Missing') != "Missing":
            status_lines.append(f"<b>Transplant:</b> {escape(format_value(patient.get('Transplant_Kidney')))}")
        if patient.get('Dialysis', 'Missing') != "Missing":
            status_lines.append(f"<b>Dialysis:</b> {escape(format_value(patient.get('Dialysis')))}")
        
        status_table = Table([[Paragraph(line, styles['CustomCenterText'], encoding='utf-8')] for line in status_lines], colWidths=[doc.width])
        status_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
        ]))
        elements.append(status_table)
        elements.append(Spacer(1, 0.5*inch))

        # Results Overview
        elements.append(Paragraph("Results Overview", styles['CustomSubTitle']))
        elements.append(Spacer(1, 0.3*inch))

        # KDIGO 2024 Classification (Centered Box)
        ckd_color, ckd_group = classify_status(patient.get('CKD_Group', 'Missing'), None, "CKD_Group")
        ckd_style = ParagraphStyle(name='CKDStyle', parent=styles['CustomTableText'], textColor=ckd_color)
        kdigo_table = Table([
            [Paragraph("<b>KDIGO 2024 Classification</b>", styles['CustomTableText'], encoding='utf-8')],
            [Paragraph(f"<b>{escape(ckd_group)}</b>", ckd_style, encoding='utf-8')]
        ], colWidths=[1.5*inch])
        kdigo_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        centered_kdigo_table = Table([[kdigo_table]], colWidths=[doc.width], rowHeights=[None])
        centered_kdigo_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(centered_kdigo_table)
        elements.append(Spacer(1, 0.3*inch))

        # Patient Information
        elements.append(Paragraph("Patient Information", styles['CustomSectionHeader']))
        patient_info_data = [
            [Paragraph(f"• <b>NHS Number:</b> {int(patient['HC_Number']) if pd.notna(patient['HC_Number']) else 'N/A'}", styles['CustomTableText'], encoding='utf-8')],
            [Paragraph(f"• <b>Age:</b> {int(patient['Age']) if pd.notna(patient['Age']) else 'N/A'} | <b>Gender:</b> {escape(format_value(patient.get('Gender')))}", styles['CustomTableText'], encoding='utf-8')]
        ]
        patient_info_table = Table(patient_info_data, colWidths=[doc.width])
        patient_info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 12),
        ]))
        elements.append(patient_info_table)
        elements.append(Spacer(1, 0.3*inch))

        # CKD Overview (Without KDIGO Classification)
        elements.append(Paragraph("CKD Overview", styles['CustomSectionHeader']))
        ckd_data = [
            [Paragraph(f"• <b>Stage:</b> {escape(format_value(patient.get('CKD_Stage')))} | <b>ACR Criteria:</b> {escape(format_value(patient.get('CKD_ACR')))}", styles['CustomTableText'], encoding='utf-8')],
            [Paragraph(f"• <b>Albumin-Creatinine Ratio (ACR):</b> <font color='#{classify_status(patient.get('ACR', 'Missing'), None, 'ACR')[0].hexval()[2:8]}'>{escape(format_value(patient.get('ACR')))} mg/mmol</font> | <b>Date:</b> {escape(format_value(patient.get('Sample_Date1')))}", styles['CustomTableText'], encoding='utf-8')],
            [Paragraph(f"• <b>Creatinine:</b>", styles['CustomTableText'], encoding='utf-8')],
            [Paragraph(f"    - <b>Current:</b> <font color='#{classify_status(patient.get('Creatinine', 'Missing'), None, 'Creatinine')[0].hexval()[2:8]}'>{escape(format_value(patient.get('Creatinine')))} µmol/L</font> | <b>Date:</b> {escape(format_value(patient.get('Sample_Date')))}", styles['CustomTableText'], encoding='utf-8')],
            [Paragraph(f"    - <b>3 Months Prior:</b> {escape(format_value(patient.get('Creatinine_3m_prior')))} µmol/L | <b>Date:</b> {escape(format_value(patient.get('Sample_Date2')))}", styles['CustomTableText'], encoding='utf-8')],
            [Paragraph(f"• <b>eGFR:</b>", styles['CustomTableText'], encoding='utf-8')],
            [Paragraph(f"    - <b>Current:</b> <font color='#{classify_status(patient.get('eGFR', 'Missing'), None, 'eGFR')[0].hexval()[2:8]}'>{escape(format_value(patient.get('eGFR')))} mL/min/1.73m²</font> | <b>Date:</b> {escape(format_value(patient.get('Sample_Date')))}", styles['CustomTableText'], encoding='utf-8')],
            [Paragraph(f"    - <b>3 Months Prior:</b> {escape(format_value(patient.get('eGFR_3m_prior')))} mL/min/1.73m² | <b>Date:</b> {escape(format_value(patient.get('Sample_Date2')))}", styles['CustomTableText'], encoding='utf-8')],
            [Paragraph(f"    - <b>eGFR Trend:</b> {escape(format_value(patient.get('eGFR_Trend')))}", styles['CustomTableText'], encoding='utf-8')]
        ]
        
        ckd_table = Table(ckd_data, colWidths=[doc.width])
        ckd_table.setStyle(TableStyle([
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 12),
        ]))
        elements.append(ckd_table)
        
        elements.append(Spacer(1, 0.1*inch))
        elements.append(Paragraph(
            "<i>The eGFR trend is assessed by comparing the most recent value with the reading from three months prior. The change is adjusted to an annualized rate based on the time interval between measurements.</i>",
            styles['CustomSmallText'],
            encoding='utf-8'
        ))
        elements.append(Paragraph(
            "• <b>Rapid Decline:</b> A decrease of more than 5 mL/min/1.73m² per year or a relative drop of 25% or more.",
            styles['CustomSmallText'],
            encoding='utf-8'
        ))
        elements.append(Paragraph(
            "• <b>Stable:</b> No significant decline.",
            styles['CustomSmallText'],
            encoding='utf-8'
        ))
        elements.append(Paragraph(
            "A rapid decline may indicate progressive CKD, requiring closer monitoring or intervention.",
            styles['CustomSmallText'],
            encoding='utf-8'
        ))
        elements.append(Spacer(1, 0.3*inch))

        # Blood Pressure
        elements.append(Paragraph("Blood Pressure", styles['CustomSectionHeader']))
        bp_color_sys, bp_value_sys = classify_status(patient.get('Systolic_BP', 'Missing'), None, 'Systolic_BP')
        bp_color_dia, bp_value_dia = classify_status(patient.get('Diastolic_BP', 'Missing'), None, 'Diastolic_BP')
        bp_data = [
            [Paragraph(f"• <b>Classification:</b> {escape(format_value(patient.get('BP_Classification')))} | <b>Date:</b> {escape(format_value(patient.get('Sample_Date3')))}", styles['CustomTableText'], encoding='utf-8')],
            [Paragraph(f"• <b>Systolic / Diastolic:</b> <font color='#{bp_color_sys.hexval()[2:8]}'>{escape(bp_value_sys)}</font> / <font color='#{bp_color_dia.hexval()[2:8]}'>{escape(bp_value_dia)}</font> mmHg", styles['CustomTableText'], encoding='utf-8')],
            [Paragraph(f"• <b>Target BP:</b> {escape(format_value(patient.get('BP_Target')))} | <b>BP Status:</b> {escape(format_value(patient.get('BP_Flag')))}", styles['CustomTableText'], encoding='utf-8')]
        ]
        bp_table = Table(bp_data, colWidths=[doc.width])
        bp_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 12),
        ]))
        elements.append(bp_table)
        elements.append(Spacer(1, 0.3*inch))

        # Anaemia Overview
        elements.append(Paragraph("Anaemia Overview", styles['CustomSectionHeader']))
        haemoglobin_color, haemoglobin_value = classify_status(patient.get('haemoglobin', 'Missing'), None, 'haemoglobin')
        anaemia_data = [
            [Paragraph(f"• <b>Haemoglobin:</b> <font color='#{haemoglobin_color.hexval()[2:8]}'>{escape(haemoglobin_value)} g/L</font> | <b>Date:</b> {escape(format_value(patient.get('Sample_Date5')))}", styles['CustomTableText'], encoding='utf-8')],
            [Paragraph(f"• <b>Current Status:</b> {escape(format_value(patient.get('Anaemia_Classification')))}", styles['CustomTableText'], encoding='utf-8')],
            [Paragraph(f"• <b>Anaemia Management:</b> {escape(format_value(patient.get('Anaemia_Flag')))}", styles['CustomTableText'], encoding='utf-8')]
        ]
        anaemia_table = Table(anaemia_data, colWidths=[doc.width])
        anaemia_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 12),
        ]))
        elements.append(anaemia_table)
        elements.append(Spacer(1, 0.3*inch))

        # Electrolyte and MBD Management
        elements.append(Paragraph("Electrolyte and Mineral Bone Disorder (MBD) Management", styles['CustomSectionHeader']))
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
            [Paragraph(f"• <b>Potassium:</b> <font color='#{classify_status(patient.get('Potassium', 'Missing'), None, 'Potassium')[0].hexval()[2:8]}'>{escape(format_value(patient.get('Potassium')))} mmol/L</font> | <b>Status:</b> {escape(format_value(patient.get('Potassium_Flag')))} | <b>Date:</b> {escape(format_value(patient.get('Sample_Date7')))}", styles['CustomTableText'], encoding='utf-8')],
            [Paragraph(f"• <b>Bicarbonate:</b> <font color='#{classify_status(patient.get('Bicarbonate', 'Missing'), None, 'Bicarbonate')[0].hexval()[2:8]}'>{escape(format_value(patient.get('Bicarbonate')))} mmol/L</font> | <b>Status:</b> {escape(format_value(patient.get('Bicarbonate_Flag')))} | <b>Date:</b> {escape(format_value(patient.get('Sample_Date13')))}", styles['CustomTableText'], encoding='utf-8')],
            [Paragraph(f"• <b>Parathyroid Hormone (PTH):</b> <font color='#{classify_status(patient.get('Parathyroid', 'Missing'), None, 'Parathyroid')[0].hexval()[2:8]}'>{escape(format_value(patient.get('Parathyroid')))} pg/mL</font> | <b>Status:</b> {escape(format_value(patient.get('Parathyroid_Flag')))} | <b>Date:</b> {escape(format_value(patient.get('Sample_Date12')))}", styles['CustomTableText'], encoding='utf-8')],
            [Paragraph(f"• <b>Phosphate:</b> <font color='#{classify_status(patient.get('Phosphate', 'Missing'), None, 'Phosphate')[0].hexval()[2:8]}'>{escape(format_value(patient.get('Phosphate')))} mmol/L</font> | <b>Status:</b> {escape(format_value(patient.get('Phosphate_Flag')))} | <b>Date:</b> {escape(format_value(patient.get('Sample_Date8')))}", styles['CustomTableText'], encoding='utf-8')],
            [Paragraph(f"• <b>Calcium:</b> <font color='#{classify_status(patient.get('Calcium', 'Missing'), None, 'Calcium')[0].hexval()[2:8]}'>{escape(format_value(patient.get('Calcium')))} mmol/L</font> | <b>Status:</b> {escape(format_value(patient.get('Calcium_Flag')))} | <b>Date:</b> {escape(format_value(patient.get('Sample_Date9')))}", styles['CustomTableText'], encoding='utf-8')]
        ]
        for value, flag, date in unique_vitamin_d:
            mbd_data.append(
                [Paragraph(f"• <b>Vitamin D Level:</b> <font color='#{classify_status(value, None, 'Vitamin_D')[0].hexval()[2:8]}'>{escape(format_value(value))} ng/mL</font> | <b>Status:</b> {escape(format_value(flag))} | <b>Date:</b> {escape(format_value(date))}", styles['CustomTableText'], encoding='utf-8')]
            )
        
        mbd_inner_table = Table(mbd_data, colWidths=[doc.width])
        mbd_inner_table.setStyle(TableStyle([
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 12),
        ]))
        
        mbd_status_table = Table([
            [Paragraph("<b>MBD Status</b>", styles['CustomTableText'], encoding='utf-8')],
            [Paragraph(f"{escape(format_value(patient.get('CKD_MBD_Flag')))}", styles['CustomTableText'], encoding='utf-8')]
        ], colWidths=[1.5*inch])
        mbd_status_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        centered_mbd_status_table = Table([[mbd_status_table]], colWidths=[doc.width], rowHeights=[None])
        centered_mbd_status_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        mbd_table = Table([[mbd_inner_table], [centered_mbd_status_table]], colWidths=[doc.width])
        mbd_table.setStyle(TableStyle([
            ('ALIGN', (0, 1), (-1, 1), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(mbd_table)
        elements.append(Spacer(1, 0.3*inch))

        # Diabetes and HbA1c Management
        elements.append(Paragraph("Diabetes and HbA1c Management", styles['CustomSectionHeader']))
        hba1c_color, hba1c_value = classify_status(patient.get('HbA1c', 'Missing'), None, 'HbA1c')
        diabetes_data = [
            [Paragraph(f"• <b>HbA1c Level:</b> <font color='#{hba1c_color.hexval()[2:8]}'>{escape(hba1c_value)} mmol/mol</font> | <b>Date:</b> {escape(format_value(patient.get('Sample_Date6')))}", styles['CustomTableText'], encoding='utf-8')],
            [Paragraph(f"• <b>HbA1c Management:</b> {escape(format_value(patient.get('HbA1c_Target')))}", styles['CustomTableText'], encoding='utf-8')]
        ]
        diabetes_table = Table(diabetes_data, colWidths=[doc.width])
        diabetes_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 12),
        ]))
        elements.append(diabetes_table)
        elements.append(Spacer(1, 0.3*inch))

        # Kidney Failure Risk
        elements.append(Paragraph("Kidney Failure Risk", styles['CustomSectionHeader']))
        risk_2yr_color, risk_2yr_value = classify_status(patient.get('risk_2yr', 'Missing'), None, 'risk_2yr')
        risk_5yr_color, risk_5yr_value = classify_status(patient.get('risk_5yr', 'Missing'), None, 'risk_5yr')
        risk_data = [
            [Paragraph(f"• <b>2-Year Risk:</b> <font color='#{risk_2yr_color.hexval()[2:8]}'>{escape(risk_2yr_value)}%</font>", styles['CustomTableText'], encoding='utf-8')],
            [Paragraph(f"• <b>5-Year Risk:</b> <font color='#{risk_5yr_color.hexval()[2:8]}'>{escape(risk_5yr_value)}%</font>", styles['CustomTableText'], encoding='utf-8')]
        ]
        risk_table = Table(risk_data, colWidths=[doc.width])
        risk_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 12),
        ]))
        elements.append(risk_table)
        elements.append(Spacer(1, 0.1*inch))
        elements.append(Paragraph(
            "<i>The patient's 2- and 5-year kidney failure risk scores estimate the likelihood that their kidney disease will progress to kidney failure within the next 2 or 5 years. These scores are calculated based on the patient's current kidney function and other risk factors such as age, blood pressure, and existing health conditions. Understanding these risk scores helps in predicting disease progression and planning appropriate treatment strategies.</i>",
            styles['CustomSmallText'],
            encoding='utf-8'
        ))
        elements.append(Spacer(1, 0.3*inch))

        # Care & Referrals
        elements.append(Paragraph("Care & Referrals", styles['CustomSectionHeader']))
        care_data = [
            [Paragraph(f"• <b>Multidisciplinary Care:</b> {escape(format_value(patient.get('Multidisciplinary_Care')))}", styles['CustomTableText'], encoding='utf-8')],
            [Paragraph(f"• <b>Modality Education:</b> {escape(format_value(patient.get('Modality_Education')))}", styles['CustomTableText'], encoding='utf-8')],
            [Paragraph(f"• <b>Nephrology Referral:</b> {escape(format_value(patient.get('Nephrology_Referral')))}", styles['CustomTableText'], encoding='utf-8')],
            [Paragraph(f"• <b>Persistent Proteinuria:</b> {escape(format_value(patient.get('Proteinuria_Flag')))}", styles['CustomTableText'], encoding='utf-8')]
        ]
        care_table = Table(care_data, colWidths=[doc.width])
        care_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 12),
        ]))
        elements.append(care_table)
        elements.append(Spacer(1, 0.3*inch))

        # Medication Review
        elements.append(Paragraph("Medication Review", styles['CustomSectionHeader']))
        med_data = [
            [Paragraph(f"• <b>Current Medication:</b> {escape(format_value(patient.get('Medications', 'None')))}", styles['CustomTableText'], encoding='utf-8')],
            [Paragraph(f"• <b>Review Medications:</b> {escape(format_value(patient.get('dose_adjustment_prescribed')))}", styles['CustomTableText'], encoding='utf-8')],
            [Paragraph(f"• <b>Contraindicated Medications:</b> {escape(format_value(patient.get('contraindicated_prescribed')))}", styles['CustomTableText'], encoding='utf-8')],
            [Paragraph(f"• <b>Suggested Medications:</b> {escape(format_value(patient.get('Recommended_Medications', 'None')))}", styles['CustomLongText'], encoding='utf-8')],
            [Paragraph(f"• <b>Statin Recommendation:</b> {escape(format_value(patient.get('Statin_Recommendation')))}", styles['CustomTableText'], encoding='utf-8')]
        ]
        med_table = Table(med_data, colWidths=[doc.width])
        med_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 12),
        ]))
        elements.append(med_table)
        elements.append(Spacer(1, 0.3*inch))

        # Lifestyle and Preventative Advice
        elements.append(Paragraph("Lifestyle and Preventative Advice", styles['CustomSectionHeader']))
        lifestyle_data = [
            [Paragraph(f"• <b>Lifestyle Recommendations:</b> {escape(format_value(patient.get('Lifestyle_Advice', 'No specific advice available.')))}", styles['CustomLongText'], encoding='utf-8')]
        ]
        lifestyle_table = Table(lifestyle_data, colWidths=[doc.width])
        lifestyle_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 11),
        ]))
        elements.append(lifestyle_table)
        elements.append(Spacer(1, 0.3*inch))

        # NICE Guideline Recommendations
        elements.append(Paragraph("NICE Guideline Recommendations", styles['CustomSubTitle']))
        elements.append(Paragraph(
            "For detailed guidance, refer to <a href='https://www.nice.org.uk/guidance/ng203'>NICE NG203 guideline on Chronic Kidney Disease</a>.",
            styles['CustomTableText'],
            encoding='utf-8'
        ))
        elements.append(Spacer(1, 0.2*inch))

        ckd_stage = patient.get('CKD_Stage', 'Unknown')
        if ckd_stage == "Normal Function":
            nice_data = [
                [Paragraph("<b>Recommendations for Normal Kidney Function</b>", styles['CustomTableText'], encoding='utf-8')],
                [Paragraph("• <b>General Health Maintenance:</b> Encourage a balanced diet and regular physical activity. Avoid excessive use of NSAIDs and other nephrotoxic agents. Regular monitoring is not required unless risk factors are present.", styles['CustomTableText'], encoding='utf-8')],
                [Paragraph("• <b>Risk Factor Management:</b> Monitor blood pressure and maintain within normal ranges. Screen for diabetes and manage blood glucose levels if necessary.", styles['CustomTableText'], encoding='utf-8')],
                [Paragraph("• <b>Preventive Measures:</b> Encourage smoking cessation and limit alcohol intake. Stay hydrated and maintain a healthy weight.", styles['CustomTableText'], encoding='utf-8')]
            ]
        elif ckd_stage == "Stage 1":
            nice_data = [
                [Paragraph("<b>CKD Stage G1 Recommendations</b>", styles['CustomTableText'], encoding='utf-8')],
                [Paragraph("• <b>Initial Assessment:</b> Perform Urine Albumin-to-Creatinine Ratio (ACR) testing to detect proteinuria, conduct haematuria screening, and monitor blood pressure (BP). Confirm stable renal function by reviewing prior estimated glomerular filtration rate (eGFR) results; if unavailable, re-evaluate renal function within 14 days.", styles['CustomTableText'], encoding='utf-8')],
                [Paragraph("• <b>Management and Monitoring:</b> Manage in primary care with annual monitoring if ACR is greater than 3 mg/mmol (indicative of microalbuminuria). If ACR is less than 3 mg/mmol, consider reducing the frequency of monitoring based on individual risk factors.", styles['CustomTableText'], encoding='utf-8')],
                [Paragraph("• <b>Lifestyle and Preventive Measures:</b> Encourage regular physical activity, smoking cessation, and maintaining a healthy weight. Aim for BP targets of less than 140/90 mmHg generally, or less than 130/80 mmHg if the patient has diabetes or an ACR greater than 70 mg/mmol (significant proteinuria).", styles['CustomTableText'], encoding='utf-8')],
                [Paragraph("• <b>Medication:</b> Assess cardiovascular risk and consider initiating statin therapy if appropriate, following current guidelines.", styles['CustomTableText'], encoding='utf-8')]
            ]
        elif ckd_stage == "Stage 2":
            nice_data = [
                [Paragraph("<b>CKD Stage G2 Recommendations</b>", styles['CustomTableText'], encoding='utf-8')],
                [Paragraph("• <b>Initial Assessment:</b> Repeat Urine ACR testing, haematuria screening, and BP monitoring as per Stage G1. Confirm stable renal function by reviewing previous eGFR results or retest within 14 days if necessary.", styles['CustomTableText'], encoding='utf-8')],
                [Paragraph("• <b>Management and Monitoring:</b> Continue primary care management with annual monitoring if ACR is greater than 3 mg/mmol. Reduce monitoring frequency if ACR is less than 3 mg/mmol and no additional risk factors are present.", styles['CustomTableText'], encoding='utf-8')],
                [Paragraph("• <b>Lifestyle and Preventive Measures:</b> Promote lifestyle interventions such as regular exercise, smoking cessation, and weight management. Maintain BP targets of less than 140/90 mmHg, or less than 130/80 mmHg for patients with diabetes or significant proteinuria (ACR >70 mg/mmol).", styles['CustomTableText'], encoding='utf-8')],
                [Paragraph("• <b>Medication:</b> Evaluate cardiovascular risk and consider statin therapy as per guidelines. If proteinuria is present, consider initiating an ACE inhibitor or angiotensin receptor blocker (ARB) to reduce proteinuria and slow CKD progression.", styles['CustomTableText'], encoding='utf-8')]
            ]
        elif ckd_stage == "Stage 3A":
            nice_data = [
                [Paragraph("<b>CKD Stage G3a Recommendations</b>", styles['CustomTableText'], encoding='utf-8')],
                [Paragraph("• <b>Monitoring and Risk Assessment:</b> Manage in primary care with at least annual renal function tests; increase monitoring to every 6 months if ACR is greater than 3 mg/mmol. Use the Kidney Failure Risk Equation (KFRE) at each assessment to estimate progression risk; refer to nephrology if the 5-year risk is greater than 5%.", styles['CustomTableText'], encoding='utf-8')],
                [Paragraph("• <b>Referral Criteria:</b> Refer to nephrology if ACR is greater than 70 mg/mmol, there’s a sustained decrease in eGFR of 25% or more over 12 months, or if significant proteinuria or haematuria is present.", styles['CustomTableText'], encoding='utf-8')],
                [Paragraph("• <b>Lifestyle and Preventive Measures:</b> Intensify cardiovascular risk management, including prescribing Atorvastatin 20 mg unless contraindicated. Maintain BP targets as per guidelines: less than 140/90 mmHg generally, or less than 130/80 mmHg if the patient has diabetes or significant proteinuria.", styles['CustomTableText'], encoding='utf-8')],
                [Paragraph("• <b>Medication:</b> Initiate or optimize ACE inhibitor or ARB therapy if proteinuria is present, unless contraindicated.", styles['CustomTableText'], encoding='utf-8')],
                [Paragraph("• <b>Patient Education:</b> Educate on CKD progression, importance of medication adherence, and regular monitoring.", styles['CustomTableText'], encoding='utf-8')]
            ]
        elif ckd_stage == "Stage 3B":
            nice_data = [
                [Paragraph("<b>CKD Stage G3b Recommendations</b>", styles['CustomTableText'], encoding='utf-8')],
                [Paragraph("• <b>Monitoring and Risk Management:</b> Continue primary care management with renal function tests every 6 months, or more frequently if ACR is greater than 3 mg/mmol. Use the KFRE to assess progression risk; refer to nephrology if the 5-year risk exceeds 5% or if there’s a rapid decline in eGFR.", styles['CustomTableText'], encoding='utf-8')],
                [Paragraph("• <b>Referral Considerations:</b> Consider nephrology referral for further evaluation and management, especially if complications like anaemia, electrolyte imbalances, or bone mineral disorders arise.", styles['CustomTableText'], encoding='utf-8')],
                [Paragraph("• <b>Lifestyle and Preventive Measures:</b> Aggressively manage BP and cardiovascular risk factors. Optimize dosing of ACE inhibitors or ARBs. Continue statin therapy as indicated.", styles['CustomTableText'], encoding='utf-8')],
                [Paragraph("• <b>Patient Education:</b> Reinforce the importance of lifestyle modifications and adherence to treatment plans to slow CKD progression.", styles['CustomTableText'], encoding='utf-8')]
            ]
        elif ckd_stage == "Stage 4":
            nice_data = [
                [Paragraph("<b>CKD Stage G4 Recommendations</b>", styles['CustomTableText'], encoding='utf-8')],
                [Paragraph("• <b>Specialist Management and Referral:</b> Routine referral to nephrology for co-management and preparation for potential renal replacement therapy. Regularly monitor eGFR, ACR, potassium, calcium, phosphate, and haemoglobin levels. Perform renal ultrasound if structural abnormalities or obstruction are suspected.", styles['CustomTableText'], encoding='utf-8')],
                [Paragraph("• <b>Management of Complications:</b> Monitor and manage anaemia, electrolyte imbalances, acidosis, and bone mineral disorders. Adjust medications that are renally excreted. Maintain BP targets as per guidelines.", styles['CustomTableText'], encoding='utf-8')],
                [Paragraph("• <b>Lifestyle and Preventive Measures:</b> Continue statin therapy (Atorvastatin 20 mg) for cardiovascular risk reduction. Provide vaccinations including influenza, pneumococcal, and COVID-19 as indicated. Regularly review medications to avoid nephrotoxic drugs and adjust dosages. Discontinue metformin if eGFR is less than 30 mL/min/1.73 m².", styles['CustomTableText'], encoding='utf-8')],
                [Paragraph("• <b>Patient Education:</b> Discuss potential need for renal replacement therapy and available options. Provide guidance on diet, fluid intake, and symptom management.", styles['CustomTableText'], encoding='utf-8')]
            ]
        elif ckd_stage == "Stage 5":
            nice_data = [
                [Paragraph("<b>CKD Stage G5 Recommendations</b>", styles['CustomTableText'], encoding='utf-8')],
                [Paragraph("• <b>Specialist Management and Comprehensive Care Plan:</b> Under specialist nephrology care with preparation for renal replacement therapy (dialysis or transplantation) as needed. Regularly monitor renal function and labs including electrolytes, bicarbonate, calcium, phosphate, haemoglobin, and fluid status.", styles['CustomTableText'], encoding='utf-8')],
                [Paragraph("• <b>Management of Complications:</b> Actively manage hyperkalaemia, metabolic acidosis, and anaemia (with iron supplementation and erythropoiesis-stimulating agents). Adjust or discontinue medications contraindicated in advanced CKD.", styles['CustomTableText'], encoding='utf-8')],
                [Paragraph("• <b>Lifestyle and Preventive Measures:</b> Continue statin therapy unless contraindicated. Provide comprehensive lifestyle guidance, including dietary advice (e.g., potassium and phosphate restrictions) and fluid management. Ensure all appropriate immunizations are up to date.", styles['CustomTableText'], encoding='utf-8')],
                [Paragraph("• <b>Patient Support and Education:</b> Offer psychological support and counseling. Educate the patient and family about end-stage renal disease management options and advance care planning.", styles['CustomTableText'], encoding='utf-8')]
            ]
        else:
            nice_data = [
                [Paragraph("<b>No specific recommendations available for this CKD stage.</b>", styles['CustomTableText'], encoding='utf-8')]
            ]

        nice_table = Table(nice_data, colWidths=[doc.width])
        nice_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 12),
        ]))
        elements.append(nice_table)
        elements.append(Spacer(1, 0.3*inch))

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
                final_recs.append([Paragraph("• <b>Renal Function Review Needed:</b> Yes", styles['CustomTableText'], encoding='utf-8')])
            recommendations = [
                ("Nephrology Referral", patient.get('Nephrology_Referral'), ["Not Indicated", "N/A", "Missing", None]),
                ("Medication Adjustments Required", patient.get('dose_adjustment_prescribed'), ["No adjustments needed", "N/A", "Missing", None]),
                ("Consider Statin Therapy", patient.get('Statin_Recommendation'), ["On Statin", "Not Indicated", "N/A", "Missing", None]),
                ("Consider Nephrology Referral", patient.get('Proteinuria_Flag'), ["No Referral Needed", "N/A", "Missing", None]),
                ("Blood Pressure Management", patient.get('BP_Target'), ["On Target", "N/A", "Missing", None])
            ]
            for title, value, ignore_list in recommendations:
                if value not in ignore_list:
                    safe_value = escape(format_value(value))
                    final_recs.append([Paragraph(f"• <b>{title}:</b> {safe_value}", styles['CustomTableText'], encoding='utf-8')])
            final_recs_table = Table(final_recs, colWidths=[doc.width])
            final_recs_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('FONTNAME', (0, 0), (-1, -1), font_name),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOX', (0, 0), (-1, -1), 1, colors.grey),
                ('PADDING', (0, 0), (-1, -1), 8),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEADING', (0, 0), (-1, -1), 12),
            ]))
            elements.append(final_recs_table)
            elements.append(Spacer(1, 0.3*inch))

        # QR Code with More Information (Combined into One Box)
        elements.append(Paragraph("More Information on Chronic Kidney Disease", styles['CustomSubTitle']))
        elements.append(Spacer(1, 7.5))  # Match HTML margin: 20px
        qr_text = "Scan this QR code with your phone to access trusted resources on <b>Chronic Kidney Disease (CKD)</b>, including <br/>guidance on managing your condition, lifestyle recommendations, and when to seek medical advice."
        qr_section = Table([
            [Image(qr_path, width=1.5*inch, height=1.5*inch) if qr_path else Paragraph("QR code unavailable", styles['CustomTableText'], encoding='utf-8')],
            [Paragraph(qr_text, styles['CustomSmallText'], encoding='utf-8')]
        ], colWidths=[doc.width])
        qr_section.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
        ]))
        elements.append(qr_section)
        elements.append(Spacer(1, 0.3*inch))

        # Surgery Contact Info
        surgery_contact_data = [
            [Paragraph(f"{surgery_info.get('surgery_name', 'Unknown Surgery')}", styles['CustomTableText'])],
            [Paragraph(f"{surgery_info.get('surgery_address_line1', 'N/A')}", styles['CustomTableText'])],
            [Paragraph(f"{surgery_info.get('surgery_address_line2', 'N/A')}" if surgery_info.get('surgery_address_line2') else "", styles['CustomTableText'])],
            [Paragraph(f"{surgery_info.get('surgery_city', 'N/A')}", styles['CustomTableText'])],
            [Paragraph(f"{surgery_info.get('surgery_postcode', 'N/A')}", styles['CustomTableText'])],
            [Paragraph(f"<b>Tel:</b> {escape(surgery_info.get('surgery_phone', 'N/A'))}", styles['CustomTableText'], encoding='utf-8')]
        ]
        surgery_contact_table = Table(surgery_contact_data, colWidths=[doc.width])
        surgery_contact_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
        ]))
        centered_surgery_contact_table = Table([[surgery_contact_table]], colWidths=[doc.width], rowHeights=[None])
        centered_surgery_contact_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(centered_surgery_contact_table)
        elements.append(Spacer(1, 0.3*inch))

        # Build the PDF with header and footer
        def add_header_footer(canvas, doc):
            canvas.saveState()
            canvas.setFont(font_name, 10)
            canvas.setFillColor(colors.black)
            canvas.drawString(doc.leftMargin, doc.pagesize[1] - doc.topMargin + 20, f"{surgery_info.get('surgery_name', 'Unknown Surgery')}")
            canvas.drawCentredString(doc.pagesize[0]/2, doc.pagesize[1] - doc.topMargin + 20, "Chronic Kidney Disease Review")
            canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, doc.pagesize[1] - doc.topMargin + 20, f"Date: {datetime.now().strftime('%Y-%m-%d')}")
            canvas.line(doc.leftMargin, doc.pagesize[1] - doc.topMargin + 10, doc.pagesize[0] - doc.rightMargin, doc.pagesize[1] - doc.topMargin + 10)
            
            canvas.setFont(font_name, 8)
            canvas.setFillColor(colors.grey)
            canvas.drawString(doc.leftMargin, doc.bottomMargin - 10, f"Page {doc.page}")
            canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, doc.bottomMargin - 10, f"Tel: {surgery_info.get('surgery_phone', 'N/A')}")
            canvas.line(doc.leftMargin, doc.bottomMargin, doc.pagesize[0] - doc.rightMargin, doc.bottomMargin)
            canvas.restoreState()

        doc.build(elements, onFirstPage=add_header_footer, onLaterPages=add_header_footer)
        logging.info(f"PDF generated successfully at {output_path}")

    for _, patient in CKD_review.iterrows():
        patient_data = patient.to_dict()
        patient_data.update(surgery_info)

        review_message = compute_review_message(patient_data)
        patient_data['review_message'] = review_message

        if patient_data.get('CKD_Group', "Missing") == "Missing" or pd.isna(patient_data.get('CKD_Group')):
            patient_data['CKD_Group'] = get_ckd_stage_acr_group(patient_data)
        logging.info(f"Patient HC_Number: {patient_data['HC_Number']}, CKD_Group: {patient_data.get('CKD_Group')}, eGFR: {patient_data.get('eGFR')}, ACR: {patient_data.get('ACR')}")

        sanitized_review_folder = map_review_message_to_folder(review_message)
        review_folder = os.path.join(date_folder, sanitized_review_folder)
        os.makedirs(review_folder, exist_ok=True)
        logging.info(f"Created review subfolder: {review_folder}")
        
        file_name = os.path.join(review_folder, f"Patient_Summary_{patient['HC_Number']}.pdf")
        create_patient_pdf(patient_data, surgery_info, file_name, qr_path, styles, font_name, font_name_bold)

        logging.info(f"Report saved as Patient_Summary_{patient['HC_Number']}.pdf in {review_folder}")

    return date_folder

# Main execution block
if __name__ == "__main__":
    try:
        input_file = os.path.join(base_path, "CKD_review.csv")
        CKD_review = pd.read_csv(input_file)
        output_folder = generate_patient_pdf(CKD_review)
        logging.info(f"All patient summaries generated in: {output_folder}")
    except FileNotFoundError:
        logging.error(f"Input file not found: {input_file}. Please ensure CKD_review.csv is generated by the pipeline.")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error during PDF generation: {str(e)}")
        sys.exit(1)