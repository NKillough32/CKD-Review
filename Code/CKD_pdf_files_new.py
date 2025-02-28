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

# Helper function to format value
def format_value(value, default="N/A"):
    return default if pd.isna(value) or value == "" or value == "Missing" else str(value)

# Helper function to classify status and return color
def classify_status(value, thresholds, field):
    if pd.isna(value) or value == "Missing":
        return colors.grey, "Missing"
    value = float(value) if isinstance(value, (int, float)) else value
    if field == "Creatinine":
        return colors.red if value > 150 else colors.orange if value >= 100 else colors.green, str(value)
    elif field == "eGFR":
        return colors.red if value < 30 else colors.orange if value < 60 else colors.blue if value < 90 else colors.green, str(value)
    elif field == "Systolic_BP":
        return colors.red if value >= 180 else colors.orange if 140 <= value < 180 else colors.blue if value < 90 else colors.green, str(value)
    elif field == "Diastolic_BP":
        return colors.red if value >= 120 else colors.orange if 90 <= value < 120 else colors.blue if value < 60 else colors.green, str(value)
    elif field == "haemoglobin":
        return colors.red if value < 80 else colors.orange if 80 <= value <= 110 else colors.green, str(value)
    elif field == "ACR":
        return colors.red if value >= 30 else colors.orange if value > 3 else colors.green, str(value)
    return colors.black, str(value)

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

    # Replace empty cells with pd.NA in all columns
    CKD_review = CKD_review.replace({"": pd.NA, None: pd.NA, pd.NA: pd.NA, np.nan: pd.NA})

    # Convert numeric columns while preserving pd.NA
    numeric_columns = ['Phosphate', 'Calcium', 'Vitamin_D', 'Parathyroid', 'Bicarbonate', 'eGFR', 'Creatinine', 
                       'Systolic_BP', 'Diastolic_BP', 'haemoglobin', 'Potassium', 'HbA1c', 'risk_2yr', 'risk_5yr', 'ACR']
    for col in numeric_columns:
        if col in CKD_review.columns:
            CKD_review[col] = pd.to_numeric(CKD_review[col], errors='coerce')

    # Function to create patient PDF using ReportLab
    def create_patient_pdf(patient, surgery_info, output_path, qr_path):
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='Critical', fontName='Helvetica-Bold', textColor=colors.red))
        styles.add(ParagraphStyle(name='Caution', fontName='Helvetica-Bold', textColor=colors.orange))
        styles.add(ParagraphStyle(name='Safe', fontName='Helvetica-Bold', textColor=colors.green))

        # Title
        title = Paragraph(f"{surgery_info.get('surgery_name', 'Unknown Surgery')}<br/>Chronic Kidney Disease Review", styles['Heading1'])
        elements.append(title)
        elements.append(Spacer(1, 12))

        # Review Status and EMIS Status
        status_text = f"Review Status: {format_value(patient.get('review_message', 'Uncategorized'))}<br/>" \
                      f"Current EMIS Status: {format_value(patient.get('EMIS_CKD_Code'))}"
        if patient.get('Transplant_Kidney', 'Missing') != "Missing" or patient.get('Dialysis', 'Missing') != "Missing":
            status_text += f"<br/>Transplant: {format_value(patient.get('Transplant_Kidney'))}" if patient.get('Transplant_Kidney', 'Missing') != "Missing" else ""
            status_text += f"<br/>Dialysis: {format_value(patient.get('Dialysis'))}" if patient.get('Dialysis', 'Missing') != "Missing" else ""
        elements.append(Paragraph(status_text, styles['Normal']))
        elements.append(Spacer(1, 12))

        # Patient Information
        patient_info = [
            [Paragraph("Patient Information", styles['Heading3'])],
            [f"NHS Number: {int(patient['HC_Number']) if pd.notna(patient['HC_Number']) else 'N/A'}"],
            [f"Age: {int(patient['Age']) if pd.notna(patient['Age']) else 'N/A'} | Gender: {format_value(patient.get('Gender'))}"]
        ]
        elements.append(Table(patient_info, colWidths=[500], style=[
            ('BOX', (0, 0), (-1, -1), 2, colors.grey),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(Spacer(1, 12))

        # CKD Overview
        ckd_color, ckd_group = classify_status(patient.get('CKD_Group', 'Missing'), None, "CKD_Group")
        ckd_data = [
            [Paragraph("CKD Overview", styles['Heading3']), Paragraph(f"KDIGO 2024 Classification<br/><font color='{ckd_color.hex_l}'>{format_value(patient.get('CKD_Group'))}</font>", styles['Normal'])],
            [f"Stage: {format_value(patient.get('CKD_Stage'))} | ACR Criteria: {format_value(patient.get('CKD_ACR'))}"],
            [f"Albumin-Creatinine Ratio (ACR): <font color='{classify_status(patient.get('ACR', 'Missing'), None, 'ACR')[0].hex_l}'>{format_value(patient.get('ACR'))} mg/mmol</font> | Date: {format_value(patient.get('Sample_Date1'))}"],
            [f"Creatinine (Current): <font color='{classify_status(patient.get('Creatinine', 'Missing'), None, 'Creatinine')[0].hex_l}'>{format_value(patient.get('Creatinine'))} µmol/L</font> | Date: {format_value(patient.get('Sample_Date'))}"],
            [f"Creatinine (3 Months Prior): {format_value(patient.get('Creatinine_3m_prior'))} µmol/L | Date: {format_value(patient.get('Sample_Date2'))}"],
            [f"eGFR (Current): <font color='{classify_status(patient.get('eGFR', 'Missing'), None, 'eGFR')[0].hex_l}'>{format_value(patient.get('eGFR'))} ml/min/1.73m²</font> | Date: {format_value(patient.get('Sample_Date'))}"],
            [f"eGFR (3 Months Prior): {format_value(patient.get('eGFR_3m_prior'))} ml/min/1.73m² | Date: {format_value(patient.get('Sample_Date2'))}"],
            [f"eGFR Trend: {format_value(patient.get('eGFR_Trend'))}"]
        ]
        elements.append(Table(ckd_data, colWidths=[450, 50], style=[
            ('BOX', (0, 0), (-1, -1), 2, colors.grey),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT')
        ]))
        elements.append(Spacer(1, 12))

        # Blood Pressure
        bp_data = [
            [Paragraph("Blood Pressure", styles['Heading3'])],
            [f"Classification: {format_value(patient.get('BP_Classification'))} | Date: {format_value(patient.get('Sample_Date3'))}"],
            [f"Systolic / Diastolic: <font color='{classify_status(patient.get('Systolic_BP', 'Missing'), None, 'Systolic_BP')[0].hex_l}'>{format_value(patient.get('Systolic_BP'))}</font> / <font color='{classify_status(patient.get('Diastolic_BP', 'Missing'), None, 'Diastolic_BP')[0].hex_l}'>{format_value(patient.get('Diastolic_BP'))}</font> mmHg"],
            [f"Target BP: {format_value(patient.get('BP_Target'))} | Status: {format_value(patient.get('BP_Flag'))}"]
        ]
        elements.append(Table(bp_data, colWidths=[500], style=[
            ('BOX', (0, 0), (-1, -1), 2, colors.grey),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(Spacer(1, 12))

        # Anaemia Overview
        anaemia_data = [
            [Paragraph("Anaemia Overview", styles['Heading3'])],
            [f"Haemoglobin: <font color='{classify_status(patient.get('haemoglobin', 'Missing'), None, 'haemoglobin')[0].hex_l}'>{format_value(patient.get('haemoglobin'))} g/L</font> | Date: {format_value(patient.get('Sample_Date5'))}"],
            [f"Current Status: {format_value(patient.get('Anaemia_Classification'))}"],
            [f"Anaemia Management: {format_value(patient.get('Anaemia_Flag'))}"]
        ]
        elements.append(Table(anaemia_data, colWidths=[500], style=[
            ('BOX', (0, 0), (-1, -1), 2, colors.grey),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(Spacer(1, 12))

        # Electrolyte and MBD Management
        mbd_data = [
            [Paragraph("Electrolyte and Mineral Bone Disorder (MBD) Management", styles['Heading3'])],
            [f"Potassium: {format_value(patient.get('Potassium'))} mmol/L | Status: {format_value(patient.get('Potassium_Flag'))} | Date: {format_value(patient.get('Sample_Date7'))}"],
            [f"Bicarbonate: {format_value(patient.get('Bicarbonate'))} mmol/L | Status: {format_value(patient.get('Bicarbonate_Flag'))} | Date: {format_value(patient.get('Sample_Date13'))}"],
            [f"Parathyroid Hormone (PTH): {format_value(patient.get('Parathyroid'))} pg/mL | Status: {format_value(patient.get('Parathyroid_Flag'))} | Date: {format_value(patient.get('Sample_Date12'))}"],
            [f"Phosphate: {format_value(patient.get('Phosphate'))} mmol/L | Status: {format_value(patient.get('Phosphate_Flag'))} | Date: {format_value(patient.get('Sample_Date8'))}"],
            [f"Calcium: {format_value(patient.get('Calcium'))} mmol/L | Status: {format_value(patient.get('Calcium_Flag'))} | Date: {format_value(patient.get('Sample_Date9'))}"],
            [f"Vitamin D Level: {format_value(patient.get('Vitamin_D'))} ng/mL | Status: {format_value(patient.get('Vitamin_D_Flag'))} | Date: {format_value(patient.get('Sample_Date10'))}"]
        ]
        elements.append(Table(mbd_data, colWidths=[500], style=[
            ('BOX', (0, 0), (-1, -1), 2, colors.grey),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(Spacer(1, 12))

        # Diabetes and HbA1c Management
        diabetes_data = [
            [Paragraph("Diabetes and HbA1c Management", styles['Heading3'])],
            [f"HbA1c Level: {format_value(patient.get('HbA1c'))} mmol/mol | Date: {format_value(patient.get('Sample_Date6'))}"],
            [f"HbA1c Management: {format_value(patient.get('HbA1c_Target'))}"]
        ]
        elements.append(Table(diabetes_data, colWidths=[500], style=[
            ('BOX', (0, 0), (-1, -1), 2, colors.grey),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(Spacer(1, 12))

        # Kidney Failure Risk
        risk_data = [
            [Paragraph("Kidney Failure Risk", styles['Heading3'])],
            [f"2-Year Risk: {format_value(patient.get('risk_2yr'))}%" ],
            [f"5-Year Risk: {format_value(patient.get('risk_5yr'))}%"]
        ]
        elements.append(Table(risk_data, colWidths=[500], style=[
            ('BOX', (0, 0), (-1, -1), 2, colors.grey),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(Spacer(1, 12))

        # Care & Referrals
        care_data = [
            [Paragraph("Care & Referrals", styles['Heading3'])],
            [f"Multidisciplinary Care: {format_value(patient.get('Multidisciplinary_Care'))}"],
            [f"Modality Education: {format_value(patient.get('Modality_Education'))}"],
            [f"Nephrology Referral: {format_value(patient.get('Nephrology_Referral'))}"],
            [f"Persistent Proteinuria: {format_value(patient.get('Proteinuria_Flag'))}"]
        ]
        elements.append(Table(care_data, colWidths=[500], style=[
            ('BOX', (0, 0), (-1, -1), 2, colors.grey),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(Spacer(1, 12))

        # Medication Review
        med_data = [
            [Paragraph("Medication Review", styles['Heading3'])],
            [f"Current Medication: {format_value(patient.get('Medications', 'None'))}"],
            [f"Review Medications: {format_value(patient.get('dose_adjustment_prescribed'))}"],
            [f"Contraindicated Medications: {format_value(patient.get('contraindicated_prescribed'))}"],
            [f"Suggested Medications: {format_value(patient.get('Recommended_Medications', 'None'))}"],
            [f"Statin Recommendation: {format_value(patient.get('Statin_Recommendation'))}"]
        ]
        elements.append(Table(med_data, colWidths=[500], style=[
            ('BOX', (0, 0), (-1, -1), 2, colors.grey),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(Spacer(1, 12))

        # Lifestyle and Preventative Advice
        lifestyle_data = [
            [Paragraph("Lifestyle and Preventative Advice", styles['Heading3'])],
            [f"Lifestyle Recommendations: {format_value(patient.get('Lifestyle_Advice', 'No specific advice available.'))}"]
        ]
        elements.append(Table(lifestyle_data, colWidths=[500], style=[
            ('BOX', (0, 0), (-1, -1), 2, colors.grey),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(Spacer(1, 12))

        # NICE Guidelines Section
        elements.append(Paragraph("NICE Guideline Recommendations", styles['Heading2']))
        elements.append(Paragraph("For detailed guidance, refer to <a href='https://www.nice.org.uk/guidance/ng203'>NICE NG203 guideline on Chronic Kidney Disease</a>.", styles['Normal']))
        elements.append(Spacer(1, 12))

        ckd_stage = patient.get('CKD_Stage', 'Unknown')
        if ckd_stage == "Normal Function":
            nice_data = [
                [Paragraph("Recommendations for Normal Kidney Function", styles['Heading3'])],
                ["General Health Maintenance: Encourage a balanced diet and regular physical activity. Avoid excessive use of NSAIDs and other nephrotoxic agents. Regular monitoring is not required unless risk factors are present."],
                ["Risk Factor Management: Monitor blood pressure and maintain within normal ranges. Screen for diabetes and manage blood glucose levels if necessary."],
                ["Preventive Measures: Encourage smoking cessation and limit alcohol intake. Stay hydrated and maintain a healthy weight."]
            ]
        elif ckd_stage == "Stage 1":
            nice_data = [
                [Paragraph("CKD Stage G1 Recommendations", styles['Heading3'])],
                ["Initial Assessment: Perform Urine Albumin-to-Creatinine Ratio (ACR) testing to detect proteinuria, conduct haematuria screening, and monitor blood pressure (BP). Confirm stable renal function by reviewing prior estimated glomerular filtration rate (eGFR) results; if unavailable, re-evaluate renal function within 14 days."],
                ["Management and Monitoring: Manage in primary care with annual monitoring if ACR is greater than 3 mg/mmol (indicative of microalbuminuria). If ACR is less than 3 mg/mmol, consider reducing the frequency of monitoring based on individual risk factors."],
                ["Lifestyle and Preventive Measures: Encourage regular physical activity, smoking cessation, and maintaining a healthy weight. Aim for BP targets of less than 140/90 mmHg generally, or less than 130/80 mmHg if the patient has diabetes or an ACR greater than 70 mg/mmol (significant proteinuria)."],
                ["Medication: Assess cardiovascular risk and consider initiating statin therapy if appropriate, following current guidelines."]
            ]
        elif ckd_stage == "Stage 2":
            nice_data = [
                [Paragraph("CKD Stage G2 Recommendations", styles['Heading3'])],
                ["Initial Assessment: Repeat Urine ACR testing, haematuria screening, and BP monitoring as per Stage G1. Confirm stable renal function by reviewing previous eGFR results or retest within 14 days if necessary."],
                ["Management and Monitoring: Continue primary care management with annual monitoring if ACR is greater than 3 mg/mmol. Reduce monitoring frequency if ACR is less than 3 mg/mmol and no additional risk factors are present."],
                ["Lifestyle and Preventive Measures: Promote lifestyle interventions such as regular exercise, smoking cessation, and weight management. Maintain BP targets of less than 140/90 mmHg, or less than 130/80 mmHg for patients with diabetes or significant proteinuria (ACR >70 mg/mmol)."],
                ["Medication: Evaluate cardiovascular risk and consider statin therapy as per guidelines. If proteinuria is present, consider initiating an ACE inhibitor or angiotensin receptor blocker (ARB) to reduce proteinuria and slow CKD progression."]
            ]
        elif ckd_stage == "Stage 3A":
            nice_data = [
                [Paragraph("CKD Stage G3a Recommendations", styles['Heading3'])],
                ["Monitoring and Risk Assessment: Manage in primary care with at least annual renal function tests; increase monitoring to every 6 months if ACR is greater than 3 mg/mmol. Use the Kidney Failure Risk Equation (KFRE) at each assessment to estimate progression risk; refer to nephrology if the 5-year risk is greater than 5%."],
                ["Referral Criteria: Refer to nephrology if ACR is greater than 70 mg/mmol, there’s a sustained decrease in eGFR of 25% or more over 12 months, or if significant proteinuria or haematuria is present."],
                ["Lifestyle and Preventive Measures: Intensify cardiovascular risk management, including prescribing Atorvastatin 20 mg unless contraindicated. Maintain BP targets as per guidelines: less than 140/90 mmHg generally, or less than 130/80 mmHg if the patient has diabetes or significant proteinuria."],
                ["Medication: Initiate or optimize ACE inhibitor or ARB therapy if proteinuria is present, unless contraindicated."],
                ["Patient Education: Educate on CKD progression, importance of medication adherence, and regular monitoring."]
            ]
        elif ckd_stage == "Stage 3B":
            nice_data = [
                [Paragraph("CKD Stage G3b Recommendations", styles['Heading3'])],
                ["Monitoring and Risk Management: Continue primary care management with renal function tests every 6 months, or more frequently if ACR is greater than 3 mg/mmol. Use the KFRE to assess progression risk; refer to nephrology if the 5-year risk exceeds 5% or if there’s a rapid decline in eGFR."],
                ["Referral Considerations: Consider nephrology referral for further evaluation and management, especially if complications like anaemia, electrolyte imbalances, or bone mineral disorders arise."],
                ["Lifestyle and Preventive Measures: Aggressively manage BP and cardiovascular risk factors. Optimize dosing of ACE inhibitors or ARBs. Continue statin therapy as indicated."],
                ["Patient Education: Reinforce the importance of lifestyle modifications and adherence to treatment plans to slow CKD progression."]
            ]
        elif ckd_stage == "Stage 4":
            nice_data = [
                [Paragraph("CKD Stage G4 Recommendations", styles['Heading3'])],
                ["Specialist Management and Referral: Routine referral to nephrology for co-management and preparation for potential renal replacement therapy. Regularly monitor eGFR, ACR, potassium, calcium, phosphate, and haemoglobin levels. Perform renal ultrasound if structural abnormalities or obstruction are suspected."],
                ["Management of Complications: Monitor and manage anaemia, electrolyte imbalances, acidosis, and bone mineral disorders. Adjust medications that are renally excreted. Maintain BP targets as per guidelines."],
                ["Lifestyle and Preventive Measures: Continue statin therapy (Atorvastatin 20 mg) for cardiovascular risk reduction. Provide vaccinations including influenza, pneumococcal, and COVID-19 as indicated. Regularly review medications to avoid nephrotoxic drugs and adjust dosages. Discontinue metformin if eGFR is less than 30 mL/min/1.73 m²."],
                ["Patient Education: Discuss potential need for renal replacement therapy and available options. Provide guidance on diet, fluid intake, and symptom management."]
            ]
        elif ckd_stage == "Stage 5":
            nice_data = [
                [Paragraph("CKD Stage G5 Recommendations", styles['Heading3'])],
                ["Specialist Management and Comprehensive Care Plan: Under specialist nephrology care with preparation for renal replacement therapy (dialysis or transplantation) as needed. Regularly monitor renal function and labs including electrolytes, bicarbonate, calcium, phosphate, haemoglobin, and fluid status."],
                ["Management of Complications: Actively manage hyperkalaemia, metabolic acidosis, and anaemia (with iron supplementation and erythropoiesis-stimulating agents). Adjust or discontinue medications contraindicated in advanced CKD."],
                ["Lifestyle and Preventive Measures: Continue statin therapy unless contraindicated. Provide comprehensive lifestyle guidance, including dietary advice (e.g., potassium and phosphate restrictions) and fluid management. Ensure all appropriate immunizations are up to date."],
                ["Patient Support and Education: Offer psychological support and counseling. Educate the patient and family about end-stage renal disease management options and advance care planning."]
            ]
        else:
            nice_data = [
                [Paragraph("No specific recommendations available for this CKD stage.", styles['Normal'])]
            ]

        elements.append(Table(nice_data, colWidths=[500], style=[
            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke)
        ]))
        elements.append(Spacer(1, 12))

        # Final Clinical Recommendations (from HTML template)
        show_recommendations = (
            patient.get('review_message', '').startswith("Review Required") or
            patient.get('Nephrology_Referral') not in ["Not Indicated", "N/A", "Missing", None] or
            patient.get('dose_adjustment_prescribed') not in ["No adjustments needed", "N/A", "Missing", None] or
            patient.get('Statin_Recommendation') not in ["On Statin", "Not Indicated", "N/A", "Missing", None] or
            patient.get('Proteinuria_Flag') not in ["No Referral Needed", "N/A", "Missing", None] or
            patient.get('BP_Flag') not in ["On Target", "N/A", "Missing", None]
        )
        
        if show_recommendations:
            final_recs = [[Paragraph("Final Clinical Recommendations", styles['Heading3'])]]
            if patient.get('review_message', '').startswith("Review Required"):
                final_recs.append(["Renal Function Review Needed: Yes"])
            recommendations = [
                ("Nephrology Referral", patient.get('Nephrology_Referral'), ["Not Indicated", "N/A", "Missing", None]),
                ("Medication Adjustments Required", patient.get('dose_adjustment_prescribed'), ["No adjustments needed", "N/A", "Missing", None]),
                ("Consider Statin Therapy", patient.get('Statin_Recommendation'), ["On Statin", "Not Indicated", "N/A", "Missing", None]),
                ("Consider Nephrology Referral", patient.get('Proteinuria_Flag'), ["No Referral Needed", "N/A", "Missing", None]),
                ("Blood Pressure Management", patient.get('BP_Target'), ["On Target", "N/A", "Missing", None])
            ]
            for title, value, ignore_list in recommendations:
                if value not in ignore_list:
                    final_recs.append([f"{title}: {format_value(value)}"])
            elements.append(Table(final_recs, colWidths=[500], style=[
                ('BOX', (0, 0), (-1, -1), 2, colors.grey),
                ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(Spacer(1, 12))

        # QR Code and Surgery Info
        elements.append(Paragraph("More Information on Chronic Kidney Disease", styles['Heading2']))
        elements.append(Paragraph("Scan this QR code with your phone to access trusted resources on Chronic Kidney Disease (CKD).", styles['Normal']))
        elements.append(Image(qr_path, width=150, height=150))
        elements.append(Spacer(1, 12))

        surgery_contact = [
            [f"{surgery_info.get('surgery_name', 'Unknown Surgery')}"],
            [f"{surgery_info.get('surgery_address_line1', 'N/A')}"],
            [f"{surgery_info.get('surgery_address_line2', 'N/A')}" if surgery_info.get('surgery_address_line2') else ""],
            [f"{surgery_info.get('surgery_city', 'N/A')}"],
            [f"{surgery_info.get('surgery_postcode', 'N/A')}"],
            [f"Tel: {surgery_info.get('surgery_phone', 'N/A')}"]
        ]
        elements.append(Table(surgery_contact, colWidths=[500], style=[
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BOX', (0, 0), (-1, -1), 1, colors.grey)
        ]))

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

# Main execution block to run the script
if __name__ == "__main__":
    # Example: Load patient data from a CSV file (adjust path as needed)
    try:
        input_file = os.path.join(base_path, "patient_data.csv")  # Replace with your actual data file path
        CKD_review = pd.read_csv(input_file)
        output_folder = generate_patient_pdf(CKD_review)
        logging.info(f"All patient summaries generated in: {output_folder}")
    except FileNotFoundError:
        logging.error(f"Input file not found: {input_file}. Please provide a valid patient data CSV.")
    except Exception as e:
        logging.error(f"Error during execution: {str(e)}")