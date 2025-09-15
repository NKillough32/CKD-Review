import pandas as pd
import os
import warnings
import re
import sys
import logging
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import KeepTogether  # Still imported but not used
from reportlab.platypus.flowables import Flowable
from reportlab.pdfgen import canvas
import qrcode
from datetime import datetime
from html import escape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime
from html.parser import HTMLParser
from xml.sax.saxutils import escape as xml_escape
from html import escape as html_escape

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler("pdf_html_generation.log")]
)

warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)

def _dedupe_meds(m):
    """Deduplicate medication strings to keep PDFs compact."""
    if pd.isna(m): return m
    items = [s.strip() for s in str(m).split(',')]
    return ', '.join(sorted(set(i for i in items if i)))

def format_date(date_str):
    if not date_str or pd.isna(date_str) or date_str == "Missing" or date_str == "N/A":
        return "N/A"
    try:
        formats = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%m/%d/%Y", "%Y.%m.%d", "%d.%m.%Y", "%d-%b-%Y", "%d %b %Y", "%b %d, %Y", "%B %d, %Y", "%d-%B-%Y", "%Y-%b-%d"]
        for fmt in formats:
            try:
                return datetime.strptime(str(date_str), fmt).strftime("%d-%m-%Y")
            except ValueError:
                continue
        parsed_date = pd.to_datetime(date_str, errors='raise')
        return parsed_date.strftime("%d-%m-%Y")
    except (ValueError, TypeError) as e:
        logging.warning(f"Could not parse date: {date_str}, Error: {str(e)}")
        return "N/A"

# Update the path setup near the top of the file
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
    working_base_path = os.getcwd()
    output_dir = os.path.join(working_base_path, "Patient_Summaries")
    dependencies_path = os.path.join(working_base_path, "Dependencies")
    surgery_info_file = os.path.join(dependencies_path, "surgery_information.csv")
else:
    base_path = os.getcwd()
    working_base_path = base_path
    output_dir = os.path.join(base_path, "Patient_Summaries")
    dependencies_path = os.path.join(base_path, "Dependencies")
    surgery_info_file = os.path.join(dependencies_path, "surgery_information.csv")

# Update the load_surgery_info function
def load_surgery_info(csv_path=surgery_info_file):
    """Load surgery information from CSV file."""
    default_info = {
        'surgery_name': 'Unknown Surgery',
        'surgery_address_line1': 'N/A',
        'surgery_address_line2': 'N/A',
        'surgery_city': 'N/A',
        'surgery_postcode': 'N/A',
        'surgery_phone': 'N/A'
    }
    
    try:
        logging.info(f"Attempting to load surgery info from: {csv_path}")
        
        if not os.path.exists(csv_path):
            logging.error(f"Surgery information file not found at: {csv_path}")
            return default_info

        surgery_df = pd.read_csv(csv_path)
        if surgery_df.empty:
            logging.error("Surgery information file is empty")
            return default_info
            
        surgery_info = surgery_df.iloc[0].to_dict()
        
        # Ensure all required fields are present
        for field in default_info.keys():
            if field not in surgery_info or pd.isna(surgery_info[field]):
                surgery_info[field] = default_info[field]
                logging.warning(f"Missing or empty field '{field}' in surgery info, using default value")
        
        logging.info(f"Successfully loaded surgery info: {surgery_info}")
        return surgery_info
        
    except Exception as e:
        logging.error(f"Error reading surgery information: {str(e)}")
        return default_info

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

def format_value(value, default="N/A"):
    if pd.isna(value) or value == "" or value == "Missing":
        return default
    formatted = str(value)
    if formatted.startswith("N/"):
        return "N/A"
    return formatted

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
        if pd.isna(value) or value == "Missing":
            return colors.grey, "Missing"
        # Safely convert to scalar value if it's a Series
        if hasattr(value, 'iloc'):
            value = value.iloc[0] if len(value) > 0 else float('nan')
        value = int(float(value))  # Convert to integer
        formatted_value = str(value)
        if value >= 180: return colors.Color(0.69, 0, 0.125), formatted_value  # #B00020
        elif 140 <= value < 180: return colors.Color(0.827, 0.329, 0), formatted_value  # #D35400
        elif value < 90: return colors.Color(0, 0, 0.545), formatted_value  # #00008B
        else: return colors.Color(0, 0.392, 0), formatted_value  # #006400
    elif field == "Diastolic_BP":
        if pd.isna(value) or value == "Missing":
            return colors.grey, "Missing"
        # Safely convert to scalar value if it's a Series
        if hasattr(value, 'iloc'):
            value = value.iloc[0] if len(value) > 0 else float('nan')
        value = int(float(value))  # Convert to integer
        formatted_value = str(value)
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
    elif field == "Potassium":
        if value < 3.5 or value > 5.5: return colors.Color(0.69, 0, 0.125), formatted_value  # #B00020
        else: return colors.Color(0, 0.392, 0), formatted_value  # #006400
    elif field == "Bicarbonate":
        if value < 22 or value > 29: return colors.Color(0.69, 0, 0.125), formatted_value  # #B00020
        else: return colors.Color(0, 0.392, 0), formatted_value  # #006400
    elif field == "Parathyroid":
        if value < 10 or value > 65: return colors.Color(0.69, 0, 0.125), formatted_value  # #B00020
        else: return colors.Color(0, 0.392, 0), formatted_value  # #006400
    elif field == "Phosphate":
        if value < 0.8 or value > 1.5: return colors.Color(0.69, 0, 0.125), formatted_value  # #B00020
        else: return colors.Color(0, 0.392, 0), formatted_value  # #006400
    elif field == "Calcium":
        if value < 2.2 or value > 2.6: return colors.Color(0.69, 0, 0.125), formatted_value  # #B00020
        else: return colors.Color(0, 0.392, 0), formatted_value  # #006400
    elif field == "Vitamin_D":
        # values assumed in nmol/L (UK)
        if value < 25:   return colors.Color(0.69, 0, 0.125), formatted_value  # Deficient
        elif value < 50: return colors.Color(0.827, 0.329, 0), formatted_value  # Insufficient
        else:            return colors.Color(0, 0.392, 0), formatted_value      # Sufficient
    elif field == "HbA1c":
        if value > 53: return colors.Color(0.69, 0, 0.125), formatted_value  # #B00020
        elif value > 48: return colors.Color(0.827, 0.329, 0), formatted_value  # #D35400
        else: return colors.Color(0, 0.392, 0), formatted_value  # #006400
    return colors.black, str(value)

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

def create_stylesheet():
    styles = getSampleStyleSheet()
    try:
        # Register regular Arial
        pdfmetrics.registerFont(TTFont('Arial', os.path.join(base_path, "Dependencies", 'Arial.ttf')))
        font_name = 'Arial'
        
        # Register Arial Bold
        pdfmetrics.registerFont(TTFont('Arial-Bold', os.path.join(base_path, "Dependencies", 'arialbd.ttf')))
        font_name_bold = 'Arial-Bold'
        
        # Register Arial Italic
        pdfmetrics.registerFont(TTFont('Arial-Italic', os.path.join(base_path, "Dependencies", 'ariali.ttf')))
        font_name_italic = 'Arial-Italic'
        
    except Exception as e:
        logging.warning(f"Failed to load Arial fonts: {str(e)}. Falling back to Helvetica.")
        font_name = 'Helvetica'
        font_name_bold = 'Helvetica-Bold'
        font_name_italic = 'Helvetica-Oblique'
    
    logging.info(f"Using fonts - Regular: {font_name}, Bold: {font_name_bold}, Italic: {font_name_italic}")

    styles.add(ParagraphStyle(name='CustomTitle', fontName=font_name_bold, fontSize=20, leading=24, alignment=1, textColor=colors.black))
    styles.add(ParagraphStyle(name='CustomSubTitle', fontName=font_name_bold, fontSize=16, leading=18, alignment=1, textColor=colors.black, spaceAfter=12))
    styles.add(ParagraphStyle(name='CustomSectionHeader', fontName=font_name_bold, fontSize=12, leading=16, alignment=0, textColor=colors.black, spaceAfter=8))
    styles.add(ParagraphStyle(name='CustomNormalText', fontName=font_name, fontSize=10, leading=12, spaceAfter=4, wordWrap='CJK'))
    styles.add(ParagraphStyle(name='CustomSmallText', fontName=font_name, fontSize=8, leading=11, spaceAfter=4, wordWrap='CJK'))
    styles.add(ParagraphStyle(name='CustomSmallTextItalics', fontName=font_name_italic, fontSize=8, leading=11, spaceAfter=4, wordWrap='CJK'))
    styles.add(ParagraphStyle(name='CustomSmallTextCenter', fontName=font_name, fontSize=8, leading=11, alignment=1, spaceAfter=4, wordWrap='CJK'))
    styles.add(ParagraphStyle(name='CustomLongText', fontName=font_name, fontSize=9, leading=11, spaceAfter=4, wordWrap='CJK'))
    styles.add(ParagraphStyle(name='CustomTableText', fontName=font_name, fontSize=10, leading=12, spaceAfter=4, wordWrap='CJK', allowWidows=1, alignment=0))
    styles.add(ParagraphStyle(name='CustomTableTexttight', fontName=font_name, fontSize=10, leading=11, spaceAfter=0, wordWrap='CJK', allowWidows=1, alignment=1))
    styles.add(ParagraphStyle(name='CustomTableTitle', fontName=font_name_bold, fontSize=10, leading=12, spaceAfter=4, wordWrap='CJK'))
    styles.add(ParagraphStyle(name='CustomTableTitleCenter', fontName=font_name_bold, fontSize=12, leading=16, alignment=1, textColor=colors.black, spaceAfter=8, wordWrap='CJK'))
    styles.add(ParagraphStyle(name='CustomCenterText', fontName=font_name, fontSize=10, leading=12, alignment=1, spaceAfter=4))#
    styles.add(ParagraphStyle(name='CustomCenterTableTexttight',parent=styles['CustomTableTexttight'],alignment=1))
    return styles, font_name, font_name_bold, font_name_italic

def draw_rounded_box(canvas, x, y, width, height, radius=5, stroke_color=colors.grey, stroke_width=1.5, fill_color=colors.whitesmoke):
    canvas.saveState()
    canvas.setStrokeColor(stroke_color)
    canvas.setFillColor(fill_color)
    canvas.setLineWidth(stroke_width)
    path = canvas.beginPath()
    path.moveTo(x + radius, y)
    path.lineTo(x + width - radius, y)
    path.curveTo(x + width - radius/2, y, x + width, y + radius/2, x + width, y + radius)
    path.lineTo(x + width, y + height - radius)
    path.curveTo(x + width, y + height - radius/2, x + width - radius/2, y + height, x + width - radius, y + height)
    path.lineTo(x + radius, y + height)
    path.curveTo(x + radius/2, y + height, x, y + height - radius/2, x, y + height - radius)
    path.lineTo(x, y + radius)
    path.curveTo(x, y + radius/2, x + radius/2, y, x + radius, y)
    canvas.drawPath(path, stroke=1, fill=1)
    canvas.restoreState()

class BoxedTable(Table):
    def __init__(self, *args, **kwargs):
        self.box_radius = kwargs.pop('box_radius', 10)
        self.box_padding = kwargs.pop('box_padding', 6)
        self.box_color = kwargs.pop('box_color', colors.grey)
        self.fill_color = kwargs.pop('fill_color', colors.whitesmoke)
        super().__init__(*args, **kwargs)
        self._width = 0
        self._height = 0

    def draw(self):
        x = self.canv._x
        y = self.canv._y
        box_x = x - self.box_padding
        box_y = y - self.box_padding
        box_width = self._width + (2 * self.box_padding)
        box_height = self._height + (2 * self.box_padding)
        draw_rounded_box(self.canv, box_x, box_y, box_width, box_height, radius=self.box_radius, stroke_color=self.box_color, fill_color=self.fill_color)
        super().draw()

def create_boxed_table(data, widths, style, radius=5, padding=6, color=colors.grey, fill_color=colors.whitesmoke):
    table = BoxedTable(
        data,
        colWidths=widths,
        box_radius=radius,
        box_padding=padding,
        box_color=color,
        fill_color=fill_color
    )
    table.setStyle(style)
    table_width, table_height = table.wrap(sum(widths), 650)
    #logging.info(f"Table height: {table_height} for data: {[str(item)[:50] for item in data]}")
    if table_height > 650 or table_height < 0:
        #logging.warning(f"Table height {table_height} invalid, forcing split. Full data: {[str(item)[:100] for item in data]}")
        table.setStyle(TableStyle([('SPLITBYROW', (0, 0), (-1, -1), True)]))
    return table

class HTMLTagChecker(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)

    def handle_endtag(self, tag):
        if tag in self.tags:
            self.tags.remove(tag)

def ensure_closed_tags(text):
    parser = HTMLTagChecker()
    parser.feed(text)
    for tag in reversed(parser.tags):
        text += f"</{tag}>"
    return text

def truncate_html_text(text, max_length=500):
    """
    Truncates text safely without cutting off in the middle of an HTML tag.
    """
    if len(text) <= max_length:
        return text  # No truncation needed

    truncated = text[:max_length]  # Truncate at max_length

    # Prevent breaking in the middle of a tag
    if "<" in truncated and ">" not in truncated:
        truncated = truncated.rsplit("<", 1)[0]  # Remove last incomplete tag

    truncated += " [Truncated]"  # Append truncation marker

    return truncated

def safe_paragraph(text, style, max_length=500, encoding='utf-8'):
    """
    Creates a safe paragraph with properly closed HTML tags.
    """
    text_str = str(text).strip()
    text_str = truncate_html_text(text_str, max_length)  # Ensure safe truncation

    # Ensure tags are properly closed
    text_str = ensure_closed_tags(text_str)

    try:
        return Paragraph(text_str, style, encoding=encoding)
    except Exception as e:
        logging.error(f"Error creating paragraph: {str(e)}")
        clean_text = re.sub(r"</?font[^>]*>", "", text_str)  # Remove all <font> tags
        clean_text = re.sub(r"</?b>", "", clean_text)  # Remove <b> tags
        return Paragraph(clean_text, style, encoding=encoding)

def generate_patient_pdf(CKD_review, template_dir=None, output_dir=output_dir):
    surgery_info = load_surgery_info()
    date_columns = [col for col in CKD_review.columns if "Date" in col]
    for date_col in date_columns:
        CKD_review[date_col] = pd.to_datetime(CKD_review[date_col], errors='coerce').dt.strftime("%d-%m-%Y")
        CKD_review[date_col] = CKD_review[date_col].apply(lambda x: "N/A" if pd.isna(x) or len(str(x)) < 10 else x)
        malformed_dates = CKD_review[date_col][CKD_review[date_col] == "N/A"]
        if not malformed_dates.empty:
            logging.warning(f"Found {len(malformed_dates)} malformed entries in {date_col}")
    logging.info(f"CKD_review columns: {list(CKD_review.columns)}")
    if 'CKD_Group' not in CKD_review.columns:
        logging.warning("CKD_Group column not found in CKD_review, computing now...")
        CKD_review['CKD_Group'] = CKD_review.apply(get_ckd_stage_acr_group, axis=1)
    date_folder = os.path.join(output_dir, datetime.now().strftime("%Y-%m-%d"))
    os.makedirs(date_folder, exist_ok=True)
    logging.info(f"Created patient summary folder: {date_folder}")
    if CKD_review.empty:
        logging.warning("CKD_review DataFrame is empty. No PDFs will be generated.")
        return date_folder
    qr_filename = "ckd_info_qr.png"
    qr_path_placeholder = os.path.join(base_path, "Dependencies", qr_filename)
    qr_path = generate_ckd_info_qr(qr_path_placeholder)
    if qr_path is None:
        qr_path = ""
        logging.warning("QR code generation failed; proceeding without QR code.")
    logging.info(f"QR Code Path: {qr_path}")
    CKD_review = CKD_review.replace({"": pd.NA, None: pd.NA, pd.NA: pd.NA, np.nan: pd.NA})
    numeric_columns = ['Phosphate', 'Calcium', 'Vitamin_D', 'Parathyroid', 'Bicarbonate', 'eGFR', 'Creatinine', 
                       'Systolic_BP', 'Diastolic_BP', 'haemoglobin', 'Potassium', 'HbA1c', 'risk_2yr', 'risk_5yr', 'ACR']
    for col in numeric_columns:
        if col in CKD_review.columns:
            CKD_review[col] = pd.to_numeric(CKD_review[col], errors='coerce')
    try:
        styles, font_name, font_name_bold, font_name_italic = create_stylesheet()
    except Exception as e:
        logging.error(f"Failed to create stylesheet: {str(e)}. Using default Helvetica fonts.")
        styles = getSampleStyleSheet()
        font_name = "Helvetica"
        font_name_bold = "Helvetica-Bold"
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
        create_patient_pdf(patient_data, surgery_info, file_name, qr_path, styles, font_name, font_name_bold, font_name_italic)
        logging.info(f"Report saved as Patient_Summary_{patient['HC_Number']}.pdf in {review_folder}")
    return date_folder

def create_patient_pdf(patient, surgery_info, output_path, qr_path, styles, font_name, font_name_bold, font_name_italic):
    for key in patient:
        if isinstance(patient[key], str) and len(patient[key]) > 1000:
            logging.warning(f"Truncating {key} for patient {patient['HC_Number']}: {patient[key][:50]}...")
            patient[key] = patient[key][:1000] + " [Truncated]"

    patient['review_message'] = compute_review_message(patient)
    if len(str(patient['review_message'])) > 1000:
        patient['review_message'] = patient['review_message'][:1000] + " [Truncated]"

    if patient.get('CKD_Group', "Missing") == "Missing" or pd.isna(patient.get('CKD_Group')):
        patient['CKD_Group'] = get_ckd_stage_acr_group(patient)
    if len(str(patient['CKD_Group'])) > 1000:
        patient['CKD_Group'] = patient['CKD_Group'][:1000] + " [Truncated]"

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,   # was: letter
        leftMargin=0.5*inch,
        rightMargin=0.5*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )
    elements = []

    # Header Section
    elements.append(safe_paragraph(f"{surgery_info.get('surgery_name', 'Unknown Surgery')}", styles['CustomTitle']))
    elements.append(Spacer(1, 0.05 * inch))
    elements.append(safe_paragraph("Chronic Kidney Disease Review", styles['CustomTitle']))
    elements.append(Spacer(1, 0.1 * inch))
    elements.append(safe_paragraph(f"<font face='{font_name_bold}'>Review Status:</font> {escape(format_value(patient.get('review_message', 'Uncategorized')))}", styles['CustomCenterText']))
    elements.append(Spacer(1, 0.025 * inch))
    elements.append(safe_paragraph(f"<font face='{font_name_bold}'>Current EMIS Status:</font> {escape(format_value(patient.get('EMIS_CKD_Code', 'N/A')))}", styles['CustomCenterText']))
    elements.append(Spacer(1, 0.05 * inch))
    if format_value(patient.get('Transplant_Kidney')) != "N/A":
        elements.append(safe_paragraph(f"<font face='{font_name_bold}'>Transplant:</font> {escape(format_value(patient.get('Transplant_Kidney')))}", styles['CustomCenterText']))
        elements.append(Spacer(1, 0.05 * inch))
    if format_value(patient.get('Dialysis')) != "N/A":
        elements.append(safe_paragraph(f"<font face='{font_name_bold}'>Dialysis:</font> {escape(format_value(patient.get('Dialysis')))}", styles['CustomCenterText']))
        elements.append(Spacer(1, 0.1 * inch))

    # KDIGO 2024 Classification
    ckd_color, ckd_group = classify_status(patient.get('CKD_Group', 'Missing'), None, "CKD_Group")
    title_style = ParagraphStyle(name='BoldTitle', parent=styles['CustomTableText'], fontName=font_name_bold, alignment=1)
    ckd_style = ParagraphStyle(name='CKDStyle', parent=styles['CustomTableText'], textColor=ckd_color, alignment=1)
    kdigo_title = safe_paragraph("KDIGO 2024 Classification", title_style)
    kdigo_status = safe_paragraph(f"<font face='{font_name_bold}'>{escape(ckd_group)}</font>", ckd_style)
    kdigo_data = [[kdigo_title], [kdigo_status]]
    kdigo_table = create_boxed_table(
        data=kdigo_data,
        widths=[150],
        style=TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('PADDING', (0, 0), (-1, -1), 12),
            ('LEADING', (0, 0), (-1, -1), 16),
        ]),
        radius=5,
        padding=6,
        color=colors.grey
    )
    centered_table = Table([[kdigo_table]], colWidths=[doc.width])
    centered_table.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
    elements.append(Spacer(1, 0.02 * inch))
    elements.append(centered_table)
    elements.append(Spacer(1, 0.35 * inch))

    # Results Title
    elements.append(safe_paragraph("Results Overview", styles['CustomSubTitle']))
    elements.append(Spacer(1, 0.025 * inch))

    # Patient Information
    id_label = "NHS Number" if str(patient.get('HC_Number','')).isdigit() and len(str(int(float(patient['HC_Number'])))) in (10,) else "HC Number"
    nhs_content = f"• <font face='{font_name_bold}'>{id_label}:</font> {escape(format_value(patient.get('HC_Number')))}"
    age_content = f"""• <font face="{font_name_bold}">Age:</font> {int(patient['Age']) if pd.notna(patient['Age']) else 'N/A'}"""
    gender_content = f"""• <font face="{font_name_bold}">Gender:</font> {escape(format_value(patient.get('Gender', 'N/A')))}"""
    
    patient_info_data = [
        [safe_paragraph(f"<font face='{font_name_bold}'>Patient Information</font>", styles['CustomSectionHeader'])],
        [safe_paragraph(nhs_content, styles['CustomTableText'])],
        [safe_paragraph(age_content, styles['CustomTableText'])],
        [safe_paragraph(gender_content, styles['CustomTableText'])]
    ]
    patient_info_table = create_boxed_table(
        data=patient_info_data,
        widths=[doc.width - 0.15 * inch],
        style=TableStyle([
            ('SPAN', (0, 0), (-1, 0)),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('PADDING', (0, 0), (-1, -1), 12),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 14),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT')
        ]),
        radius=5,
        padding=6,
        color=colors.grey
    )
    elements.append(patient_info_table)
    elements.append(Spacer(1, 0.35 * inch))

    # CKD Overview
    ckd_title = safe_paragraph("<b>CKD Overview</b>", styles['CustomSectionHeader'])
    acr_color, acr_value = classify_status(patient.get('ACR', 'Missing'), None, 'ACR')
    creatinine_color, creatinine_value = classify_status(patient.get('Creatinine', 'Missing'), None, 'Creatinine')
    egfr_color, egfr_value = classify_status(patient.get('eGFR', 'Missing'), None, 'eGFR')
    ckd_data = [
        [ckd_title],
        [safe_paragraph(f"• <font face='{font_name_bold}'>Stage:</font> {escape(format_value(patient.get('CKD_Stage')))} | "
                        f"<font face='{font_name_bold}'>ACR Criteria:</font> {escape(format_value(patient.get('CKD_ACR')))}", styles['CustomTableText'])],
        [safe_paragraph(f"• <font face='{font_name_bold}'>Albumin-Creatinine Ratio (ACR):</font> "
                        f"<font color='#{acr_color.hexval()[2:8]}'>{escape(acr_value)} mg/mmol</font> | "
                        f"<font face='{font_name_bold}'>Date:</font> {escape(format_value(patient.get('Sample_Date1')))}", styles['CustomTableText'])],
        [safe_paragraph(f"• <font face='{font_name_bold}'>Creatinine:</font>", styles['CustomTableText'])],
        [safe_paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;· <font face='{font_name_bold}'>Current:</font> "
                        f"<font color='#{creatinine_color.hexval()[2:8]}'>{escape(creatinine_value)} µmol/L</font> | "
                        f"<font face='{font_name_bold}'>Date:</font> {escape(format_value(patient.get('Sample_Date')))}", styles['CustomTableText'])],
        [safe_paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;· <font face='{font_name_bold}'>3 Months Prior:</font> "
                        f"{escape(format_value(patient.get('Creatinine_3m_prior')))} µmol/L | "
                        f"<font face='{font_name_bold}'>Date:</font> {escape(format_value(patient.get('Sample_Date2')))}", styles['CustomTableText'])],
        [safe_paragraph(f"• <font face='{font_name_bold}'>eGFR:</font>", styles['CustomTableText'])],
        [safe_paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;· <font face='{font_name_bold}'>Current:</font> "
                        f"<font color='#{egfr_color.hexval()[2:8]}'>{escape(egfr_value)} mL/min/1.73m²</font> | "
                        f"<font face='{font_name_bold}'>Date:</font> {escape(format_value(patient.get('Sample_Date')))}", styles['CustomTableText'])],
        [safe_paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;· <font face='{font_name_bold}'>3 Months Prior:</font> "
                        f"{escape(format_value(patient.get('eGFR_3m_prior')))} mL/min/1.73m² | "
                        f"<font face='{font_name_bold}'>Date:</font> {escape(format_value(patient.get('Sample_Date2')))}", styles['CustomTableText'])],
        [safe_paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;· <font face='{font_name_bold}'>eGFR Trend:</font> "
                        f"{escape(format_value(patient.get('eGFR_Trend')))}", styles['CustomTableText'])],
        [Spacer(1, 0.025 * inch)],
        [safe_paragraph("The eGFR trend is assessed by comparing the most recent value with the reading from three months prior. The change is adjusted to an annualized rate based on the time interval between measurements.", styles['CustomSmallTextItalics'])],
        [safe_paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;· <font face='{font_name_bold}'>Rapid Decline:</font> A decrease of more than 5 mL/min/1.73m² per year or a relative drop of 25% or more.", styles['CustomSmallText'])],
        [safe_paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;· <font face='{font_name_bold}'>Stable:</font> No significant decline.", styles['CustomSmallText'])],
        [safe_paragraph("A rapid decline may indicate progressive CKD, requiring closer monitoring or intervention.", styles['CustomSmallTextItalics'])],
        [Spacer(1, 0.025 * inch)]]

    ckd_table = create_boxed_table(
        data=ckd_data,
        widths=[doc.width - 0.15 * inch],
        style=TableStyle([
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 12),
            ('SPLITBYROW', (0, 0), (-1, -1), True)
        ]),
        radius=5,
        padding=6,
        color=colors.grey
    )
    elements.append(ckd_table)
    elements.append(Spacer(1, 0.35 * inch))

    # Blood Pressure
    bp_title = safe_paragraph("<b>Blood Pressure</b>", styles['CustomSectionHeader'])
    bp_color_sys, bp_value_sys = classify_status(patient.get('Systolic_BP', 'Missing'), None, 'Systolic_BP')
    bp_color_dia, bp_value_dia = classify_status(patient.get('Diastolic_BP', 'Missing'), None, 'Diastolic_BP')
    bp_data = [
        [bp_title],
        [safe_paragraph(f"• <font face='{font_name_bold}'>Classification:</font> {escape(format_value(patient.get('BP_Classification')))} | "
                        f"<font face='{font_name_bold}'>Date:</font> {escape(format_value(patient.get('Sample_Date3')))}", styles['CustomTableText'])],
        [safe_paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;· <font face='{font_name_bold}'>Systolic:</font> "
                        f"<font color='#{bp_color_sys.hexval()[2:8]}'>{escape(bp_value_sys)} mmHg</font>", styles['CustomTableText'])],
        [safe_paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;· <font face='{font_name_bold}'>Diastolic:</font> "
                        f"<font color='#{bp_color_dia.hexval()[2:8]}'>{escape(bp_value_dia)} mmHg</font>", styles['CustomTableText'])],
        [safe_paragraph(f"• <font face='{font_name_bold}'>Target BP:</font> {escape(format_value(patient.get('BP_Target')))} | "
                        f"<font face='{font_name_bold}'>BP Status:</font> {escape(format_value(patient.get('BP_Flag')))}", styles['CustomTableText'])]
    ]
    bp_table = create_boxed_table(
        data=bp_data,
        widths=[doc.width - 0.15 * inch],
        style=TableStyle([
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 12),
            ('SPLITBYROW', (0, 0), (-1, -1), True)
        ]),
        radius=5,
        padding=6,
        color=colors.grey
    )
    elements.append(bp_table)
    elements.append(Spacer(1, 0.35 * inch))

    # Anaemia Overview
    anaemia_title = safe_paragraph("<b>Anaemia Overview</b>", styles['CustomSectionHeader'])
    haemoglobin_color, haemoglobin_value = classify_status(patient.get('haemoglobin', 'Missing'), None, 'haemoglobin')
    anaemia_data = [
        [anaemia_title],
        [safe_paragraph(f"• <font face='{font_name_bold}'>Haemoglobin:</font> "
                        f"<font color='#{haemoglobin_color.hexval()[2:8]}'>{escape(haemoglobin_value)} g/L</font> | "
                        f"<font face='{font_name_bold}'>Date:</font> {escape(format_value(patient.get('Sample_Date5')))}", styles['CustomTableText'])],
        [safe_paragraph(f"• <font face='{font_name_bold}'>Current Status:</font> "
                        f"{escape(format_value(patient.get('Anaemia_Classification')))}", styles['CustomTableText'])],
        [safe_paragraph(f"• <font face='{font_name_bold}'>Anaemia Management:</font> "
                        f"{escape(format_value(patient.get('Anaemia_Flag')))}", styles['CustomTableText'])]
    ]
    anaemia_table = create_boxed_table(
        data=anaemia_data,
        widths=[doc.width - 0.15 * inch],
        style=TableStyle([
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 12),
            ('SPLITBYROW', (0, 0), (-1, -1), True)
        ]),
        radius=5,
        padding=6,
        color=colors.grey
    )
    elements.append(anaemia_table)
    elements.append(Spacer(1, 0.35 * inch))

    # Electrolyte and MBD Management
    mbd_title = safe_paragraph("<b>Electrolyte and Mineral Bone Disorder (MBD) Management</b>", styles['CustomSectionHeader'])
    potassium_color, potassium_value = classify_status(patient.get('Potassium', 'Missing'), None, 'Potassium')
    bicarbonate_color, bicarbonate_value = classify_status(patient.get('Bicarbonate', 'Missing'), None, 'Bicarbonate')
    parathyroid_color, parathyroid_value = classify_status(patient.get('Parathyroid', 'Missing'), None, 'Parathyroid')
    phosphate_color, phosphate_value = classify_status(patient.get('Phosphate', 'Missing'), None, 'Phosphate')
    calcium_color, calcium_value = classify_status(patient.get('Calcium', 'Missing'), None, 'Calcium')
    vitamin_d_entries = [(patient.get('Vitamin_D', 'Missing'), patient.get('Vitamin_D_Flag', 'Missing'), patient.get('Sample_Date10', 'Missing'))]
    seen_vitamin_d = set()
    unique_vitamin_d = []
    for value, flag, date in vitamin_d_entries:
        entry = (value, flag, date)
        if entry not in seen_vitamin_d and value not in [None, "Missing", "N/A"]:
            seen_vitamin_d.add(entry)
            unique_vitamin_d.append(entry)
        else:
            logging.warning(f"Patient HC_Number: {patient['HC_Number']}, duplicate or invalid Vitamin D entry: {value}, {flag}, {date}")
    mbd_data = [
        [mbd_title],
        [safe_paragraph(f"• <font face='{font_name_bold}'>Potassium:</font> "
                        f"<font color='#{potassium_color.hexval()[2:8]}'>{escape(potassium_value)} mmol/L</font> | "
                        f"<font face='{font_name_bold}'>Status:</font> {escape(format_value(patient.get('Potassium_Flag')))} | "
                        f"<font face='{font_name_bold}'>Date:</font> {escape(format_value(patient.get('Sample_Date7')))}", styles['CustomTableText'])],
        [safe_paragraph(f"• <font face='{font_name_bold}'>Bicarbonate:</font> "
                        f"<font color='#{bicarbonate_color.hexval()[2:8]}'>{escape(bicarbonate_value)} mmol/L</font> | "
                        f"<font face='{font_name_bold}'>Status:</font> {escape(format_value(patient.get('Bicarbonate_Flag')))} | "
                        f"<font face='{font_name_bold}'>Date:</font> {escape(format_value(patient.get('Sample_Date13')))}", styles['CustomTableText'])],
        [safe_paragraph(f"• <font face='{font_name_bold}'>Parathyroid Hormone (PTH):</font> "
                        f"<font color='#{parathyroid_color.hexval()[2:8]}'>{escape(parathyroid_value)}</font> | "
                        f"<font face='{font_name_bold}'>Status:</font> {escape(format_value(patient.get('Parathyroid_Flag')))} | "
                        f"<font face='{font_name_bold}'>Date:</font> {escape(format_value(patient.get('Sample_Date12')))}", styles['CustomTableText'])],
        [safe_paragraph(f"• <font face='{font_name_bold}'>Phosphate:</font> "
                        f"<font color='#{phosphate_color.hexval()[2:8]}'>{escape(phosphate_value)} mmol/L</font> | "
                        f"<font face='{font_name_bold}'>Status:</font> {escape(format_value(patient.get('Phosphate_Flag')))} | "
                        f"<font face='{font_name_bold}'>Date:</font> {escape(format_value(patient.get('Sample_Date8')))}", styles['CustomTableText'])],
        [safe_paragraph(f"• <font face='{font_name_bold}'>Calcium:</font> "
                        f"<font color='#{calcium_color.hexval()[2:8]}'>{escape(calcium_value)} mmol/L</font> | "
                        f"<font face='{font_name_bold}'>Status:</font> {escape(format_value(patient.get('Calcium_Flag')))} | "
                        f"<font face='{font_name_bold}'>Date:</font> {escape(format_value(patient.get('Sample_Date9')))}", styles['CustomTableText'])]
    ]
    for value, flag, date in unique_vitamin_d:
        vit_d_color, vit_d_value = classify_status(value, None, 'Vitamin_D')
        mbd_data.append(
            [safe_paragraph(f"• <font face='{font_name_bold}'>Vitamin D Level:</font> "
                            f"<font color='#{vit_d_color.hexval()[2:8]}'>{escape(vit_d_value)} nmol/L</font> | "  # was ng/mL
                            f"<font face='{font_name_bold}'>Status:</font> {escape(format_value(flag))} | "
                            f"<font face='{font_name_bold}'>Date:</font> {escape(format_value(date))}", styles['CustomTableText'])]
        )
    mbd_status_style = ParagraphStyle(name='MBDStatusStyle', parent=styles['CustomTableText'], alignment=1)
    mbd_status_table = create_boxed_table(
        data=[
            [safe_paragraph("<b>MBD Status</b>", styles['CustomTableTitleCenter'])],
            [safe_paragraph(f"{escape(format_value(patient.get('CKD_MBD_Flag')))}", mbd_status_style)]
        ],
        widths=[2 * inch],
        style=TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]),
        radius=5,
        padding=4,
        color=colors.grey
    )
    mbd_status_wrapper = Table([[mbd_status_table]], colWidths=[doc.width - 0.15 * inch])
    mbd_status_wrapper.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    mbd_data.append([mbd_status_wrapper])
    mbd_table = create_boxed_table(
        data=mbd_data,
        widths=[doc.width - 0.15 * inch],
        style=TableStyle([
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 12),
            ('SPLITBYROW', (0, 0), (-1, -1), True)
        ]),
        radius=5,
        padding=6,
        color=colors.grey
    )
    logging.info(f"Appending MBD table for patient {patient['HC_Number']}")
    elements.append(mbd_table)
    elements.append(Spacer(1, 0.35 * inch))

    # Diabetes and HbA1c Management
    diabetes_title = safe_paragraph("<b>Diabetes and HbA1c Management</b>", styles['CustomSectionHeader'])
    hba1c_color, hba1c_value = classify_status(patient.get('HbA1c', 'Missing'), None, 'HbA1c')
    diabetes_data = [
        [diabetes_title],
        [safe_paragraph(f"• <font face='{font_name_bold}'>HbA1c Level:</font> "
                        f"<font color='#{hba1c_color.hexval()[2:8]}'>{escape(hba1c_value)} mmol/mol</font> | "
                        f"<font face='{font_name_bold}'>Date:</font> {escape(format_value(patient.get('Sample_Date6')))}", styles['CustomTableText'])],
        [safe_paragraph(f"• <font face='{font_name_bold}'>HbA1c Management:</font> "
                        f"{escape(format_value(patient.get('HbA1c_Target')))}", styles['CustomTableText'])]
    ]
    diabetes_table = create_boxed_table(
        data=diabetes_data,
        widths=[doc.width - 0.15 * inch],
        style=TableStyle([
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 12),
            ('SPLITBYROW', (0, 0), (-1, -1), True)
        ]),
        radius=5,
        padding=6,
        color=colors.grey
    )
    elements.append(diabetes_table)
    elements.append(Spacer(1, 0.35 * inch))

    # Kidney Failure Risk
    risk_title = safe_paragraph("<b>Kidney Failure Risk</b>", styles['CustomSectionHeader'])
    risk_2yr_color, risk_2yr_value = classify_status(patient.get('risk_2yr', 'Missing'), None, 'risk_2yr')
    risk_5yr_color, risk_5yr_value = classify_status(patient.get('risk_5yr', 'Missing'), None, 'risk_5yr')
    risk_data = [
        [risk_title],
        [safe_paragraph(f"• <font face='{font_name_bold}'>2-Year Risk:</font> "
                        f"<font color='#{risk_2yr_color.hexval()[2:8]}'>{escape(risk_2yr_value)}%</font>", styles['CustomTableText'])],
        [safe_paragraph(f"• <font face='{font_name_bold}'>5-Year Risk:</font> "
                        f"<font color='#{risk_5yr_color.hexval()[2:8]}'>{escape(risk_5yr_value)}%</font>", styles['CustomTableText'])],
        [safe_paragraph("The patient's 2- and 5-year kidney failure risk scores estimate the likelihood that their kidney disease will progress to kidney failure within the next 2 or 5 years. These scores are calculated based on the patient's current kidney function and other risk factors such as age, blood pressure, and existing health conditions. Understanding these risk scores helps in predicting disease progression and planning appropriate treatment strategies.", styles['CustomSmallTextItalics'])]
    ]
    risk_table = create_boxed_table(
        data=risk_data,
        widths=[doc.width - 0.15 * inch],
        style=TableStyle([
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 12),
            ('SPLITBYROW', (0, 0), (-1, -1), True)
        ]),
        radius=5,
        padding=6,
        color=colors.grey
    )
    elements.append(risk_table)
    elements.append(Spacer(1, 0.35 * inch))

    # Care & Referrals
    care_title = safe_paragraph("<b>Care & Referrals</b>", styles['CustomSectionHeader'])
    care_data = [
        [care_title],
        [safe_paragraph(f"• <font face='{font_name_bold}'>Multidisciplinary Care:</font> "
                        f"{escape(format_value(patient.get('Multidisciplinary_Care')))}", styles['CustomTableText'])],
        [safe_paragraph(f"• <font face='{font_name_bold}'>Modality Education:</font> "
                        f"{escape(format_value(patient.get('Modality_Education')))}", styles['CustomTableText'])],
        [safe_paragraph(f"• <font face='{font_name_bold}'>Nephrology Referral:</font> "
                        f"{escape(format_value(patient.get('Nephrology_Referral')))}", styles['CustomTableText'])],
        [safe_paragraph(f"• <font face='{font_name_bold}'>Proteinuria:</font> "
                        f"{escape(format_value(patient.get('Proteinuria_Flag')))}", styles['CustomTableText'])]
    ]
    care_table = create_boxed_table(
        data=care_data,
        widths=[doc.width - 0.15 * inch],
        style=TableStyle([
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 12),
            ('SPLITBYROW', (0, 0), (-1, -1), True)
        ]),
        radius=5,
        padding=6,
        color=colors.grey
    )
    elements.append(care_table)
    elements.append(Spacer(1, 0.35 * inch))

    # Medication Review
    # Deduplicate medications before displaying
    patient['Medications'] = _dedupe_meds(patient.get('Medications'))
    
    med_title = safe_paragraph("<b>Medication Review</b>", styles['CustomSectionHeader'])
    current_meds = escape(format_value(patient.get('Medications', 'None')))
    med_data = [
        [med_title],
        [safe_paragraph(f"• <font face='{font_name_bold}'>Current Medication:</font> {xml_escape(format_value(patient.get('Medications', 'None')))}", 
                styles['CustomTableText'])],
        [safe_paragraph(f"• <font face='{font_name_bold}'>Dose Adjustment Medications:</font> " + 
                    escape(format_value(patient.get('dose_adjustment_prescribed', 'N/A'))), 
                    styles['CustomTableText'])],
        [safe_paragraph(f"• <font face='{font_name_bold}'>Contraindicated Medications:</font> " +
                    escape(format_value(patient.get('contraindicated_prescribed', 'N/A'))), 
                    styles['CustomTableText'])],
        [safe_paragraph(f"• <font face='{font_name_bold}'>Suggested Medications:</font> " +
                    escape(format_value(patient.get('Recommended_Medications', 'None'))), 
                    styles['CustomLongText'])],
        [safe_paragraph(f"• <font face='{font_name_bold}'>Statin Recommendation:</font> " +
                    escape(format_value(patient.get('Statin_Recommendation', 'N/A'))), 
                    styles['CustomTableText'])],
        [safe_paragraph(f"• <font face='{font_name_bold}'>SGLT2i Recommendation:</font> " +
                    escape(format_value(patient.get('SGLT2i_Recommendation', 'N/A'))), 
                    styles['CustomTableText'])]
    ]
    med_table = create_boxed_table(
        data=med_data,
        widths=[doc.width - 0.15 * inch],
        style=TableStyle([
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 12)
        ]),
        radius=5,
        padding=6,
        color=colors.grey
    )
    elements.append(KeepTogether(med_table))
    elements.append(Spacer(1, 0.35 * inch))

    # Lifestyle and Preventative Advice
    lifestyle_title = safe_paragraph("<b>Lifestyle and Preventative Advice</b>", styles['CustomSectionHeader'])
    lifestyle_data = [
        [lifestyle_title],
        [safe_paragraph(f"• <font face='{font_name_bold}'>Lifestyle Recommendations:</font> "
                        f"{escape(format_value(patient.get('Lifestyle_Advice', 'No specific advice available.')))}", styles['CustomLongText'])]
    ]
    lifestyle_table = create_boxed_table(
        data=lifestyle_data,
        widths=[doc.width - 0.15 * inch],
        style=TableStyle([
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 12),
            ('SPLITBYROW', (0, 0), (-1, -1), True)
        ]),
        radius=5,
        padding=6,
        color=colors.grey
    )
    elements.append(lifestyle_table)
    elements.append(Spacer(1, 0.35 * inch))

    # NICE Guideline Recommendations
    nice_title = safe_paragraph("<b>NICE Guideline Recommendations</b>", styles['CustomSubTitle'])
    nice_data = [
        [nice_title],
        [safe_paragraph("For detailed guidance, refer to <a href='https://www.nice.org.uk/guidance/ng203' color='#00008B'><font color='#00008B'>NICE NG203 guideline on Chronic Kidney Disease</font></a>.", styles['CustomTableText'])]
    ]
    ckd_stage = patient.get('CKD_Stage', 'Unknown')
    if ckd_stage == "Normal Function":
        nice_data.extend([
            [safe_paragraph(f"<font face='{font_name_bold}'>NICE Recommendations for Normal Kidney Function</font>", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Monitoring:</font> Regular monitoring is not required unless risk factors are present.", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Blood Pressure:</font> Monitor and maintain within normal ranges (less than 140/90 mmHg).", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Lifestyle:</font> Maintain a balanced diet, regular physical activity, and healthy weight. Encourage smoking cessation and limit alcohol intake.", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Medications:</font> Avoid excessive use of NSAIDs and other nephrotoxic agents. No specific renal medications required.", styles['CustomTableText'])]
        ])
    elif ckd_stage == "Stage 1":
        nice_data.extend([
            [safe_paragraph(f"<font face='{font_name_bold}'>NICE Recommendations for CKD Stage 1</font>", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Monitoring:</font> Annual monitoring if ACR > 3 mg/mmol. Less frequent if ACR < 3 mg/mmol without other risk factors.", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Blood Pressure:</font> Target < 140/90 mmHg generally, or < 130/80 mmHg with diabetes or ACR > 70 mg/mmol.", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Laboratory Tests:</font> Regular ACR testing, haematuria screening, and eGFR monitoring. Re-evaluate renal function within 14 days if no prior results.", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Management:</font> Primary care-based. Consider cardiovascular risk assessment and appropriate statin therapy.", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Lifestyle:</font> Encourage regular exercise, smoking cessation, and maintaining healthy weight.", styles['CustomTableText'])]
        ])
    elif ckd_stage == "Stage 2":
        nice_data.extend([
            [safe_paragraph(f"<font face='{font_name_bold}'>NICE Recommendations for CKD Stage 2</font>", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Monitoring:</font> Annual monitoring with ACR > 3 mg/mmol. Consider less frequent monitoring if ACR < 3 mg/mmol and stable.", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Blood Pressure:</font> Target < 140/90 mmHg, or < 130/80 mmHg with diabetes or significant proteinuria.", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Laboratory Tests:</font> Regular ACR, haematuria screening, and eGFR monitoring. Confirm stability with repeat testing.", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Medications:</font> Consider ACE inhibitor or ARB if proteinuria present. Evaluate need for statin therapy.", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Lifestyle:</font> Regular exercise, weight management, smoking cessation, and dietary advice.", styles['CustomTableText'])]
        ])
    elif ckd_stage == "Stage 3A":
        nice_data.extend([
            [safe_paragraph(f"<font face='{font_name_bold}'>NICE Recommendations for CKD Stage 3A</font>", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Monitoring:</font> 6-monthly monitoring with ACR > 3 mg/mmol, annual if stable and ACR < 3 mg/mmol.", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Blood Pressure:</font> Target < 140/90 mmHg, or < 130/80 mmHg with diabetes or significant proteinuria.", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Referral Criteria:</font> Refer to nephrology if ACR > 70 mg/mmol, rapid eGFR decline (>25% in 12 months), or 5-year risk > 5%.", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Medications:</font> Prescribe Atorvastatin 20mg unless contraindicated. Optimize ACE inhibitor/ARB if proteinuria present.", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Risk Assessment:</font> Regular KFRE calculation to estimate progression risk.", styles['CustomTableText'])]
        ])
    elif ckd_stage == "Stage 3B":
        nice_data.extend([
            [safe_paragraph(f"<font face='{font_name_bold}'>NICE Recommendations for CKD Stage 3B</font>", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Monitoring:</font> Minimum 6-monthly renal function tests. More frequent if rapid progression or complications.", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Nephrology Input:</font> Consider referral, especially with complications or 5-year risk > 5%.", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Complications:</font> Monitor for anaemia, electrolyte imbalances, and bone mineral disorders.", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Medications:</font> Optimize ACE inhibitor/ARB therapy. Continue statin therapy. Review medication doses.", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Education:</font> Discuss progression risk and importance of treatment adherence.", styles['CustomTableText'])]
        ])
    elif ckd_stage == "Stage 4":
        nice_data.extend([
            [safe_paragraph(f"<font face='{font_name_bold}'>NICE Recommendations for CKD Stage 4</font>", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Specialist Care:</font> Regular nephrology review for co-management and RRT planning.", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Monitoring:</font> Regular comprehensive testing including eGFR, electrolytes, bone profile, and haemoglobin.", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Medications:</font> Review and adjust all medications. Stop nephrotoxic drugs. Discontinue metformin if eGFR < 30.", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Preventive Care:</font> Ensure vaccinations up to date. Continue statin therapy unless contraindicated.", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Patient Support:</font> Discuss RRT options and provide dietary/lifestyle guidance.", styles['CustomTableText'])]
        ])
    elif ckd_stage == "Stage 5":
        nice_data.extend([
            [safe_paragraph(f"<font face='{font_name_bold}'>NICE Recommendations for CKD Stage 5</font>", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Specialist Management:</font> Close nephrology supervision with comprehensive care plan.", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Monitoring:</font> Frequent monitoring of renal function, electrolytes, acid-base status, and other parameters.", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Complications:</font> Active management of anaemia, electrolyte disorders, and metabolic acidosis.", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>RRT Planning:</font> Detailed discussion and preparation for dialysis/transplantation as appropriate.", styles['CustomTableText'])],
            [safe_paragraph(f"• <font face='{font_name_bold}'>Support:</font> Comprehensive dietary advice, psychological support, and advance care planning.", styles['CustomTableText'])]
        ])
    else:
        nice_data.append([safe_paragraph(f"<font face='{font_name_bold}'>No specific recommendations available for this CKD stage.</font>", styles['CustomTableText'])])
    nice_table = create_boxed_table(
        data=nice_data,
        widths=[doc.width - 0.15 * inch],
        style=TableStyle([
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 12),
            ('SPLITBYROW', (0, 0), (-1, -1), True)
        ]),
        radius=5,
        padding=6,
        color=colors.grey
    )
    elements.append(nice_table)
    elements.append(Spacer(1, 0.35 * inch))

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
        final_title = safe_paragraph("<b>Final Clinical Recommendations</b>", styles['CustomSectionHeader'])
        final_recs = [[final_title]]
        if patient.get('review_message', '').startswith("Review Required"):
            final_recs.append([safe_paragraph(f"• <font face='{font_name_bold}'>Renal Function Review Needed:</font> Yes", styles['CustomTableText'])])
        recommendations = [
            ("Nephrology Referral", patient.get('Nephrology_Referral'), ["Not Indicated", "N/A", "Missing", None]),
            ("Medication Adjustments Required", patient.get('dose_adjustment_prescribed'), ["No adjustments needed", "N/A", "Missing", None]),
            ("Consider Statin Therapy", patient.get('Statin_Recommendation'), ["On Statin", "Not Indicated", "N/A", "Missing", None]),
            ("Consider Nephrology Referral", patient.get('Proteinuria_Flag'), ["No Referral Needed", "N/A", "Missing", None]),
            ("Blood Pressure Management", patient.get('BP_Flag'), ["On Target", "N/A", "Missing", None])
        ]
        for title, value, ignore_list in recommendations:
            if value not in ignore_list:
                safe_value = escape(format_value(value))
                final_recs.append([safe_paragraph(f"• <font face='{font_name_bold}'>{title}:</font> {safe_value}", styles['CustomTableText'])])
        final_recs_table = create_boxed_table(
            data=final_recs,
            widths=[doc.width - 0.15 * inch],
            style=TableStyle([
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('FONTNAME', (0, 0), (-1, -1), font_name),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('PADDING', (0, 0), (-1, -1), 8),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEADING', (0, 0), (-1, -1), 12),
                ('SPLITBYROW', (0, 0), (-1, -1), True)
            ]),
            radius=5,
            padding=6,
            color=colors.grey
        )
        elements.append(KeepTogether(final_recs_table))
        elements.append(Spacer(1, 0.35 * inch))

    # QR Code Section
    qr_title = safe_paragraph("<b>More Information on Chronic Kidney Disease</b>", styles['CustomSubTitle'])
    qr_text = "Scan this QR code with your phone to access trusted resources on <b>Chronic Kidney Disease (CKD)</b>, including <br/>guidance on managing your condition, lifestyle recommendations, and when to seek medical advice."
    qr_data = [
        [qr_title],
        [Image(qr_path, width=1.5 * inch, height=1.5 * inch) if qr_path else safe_paragraph("QR code unavailable", styles['CustomTableText'])],
        [safe_paragraph(qr_text, styles['CustomSmallTextCenter'])]
    ]
    qr_section = create_boxed_table(
        data=qr_data,
        widths=[doc.width - 0.15 * inch],
        style=TableStyle([
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (0, 1), (-1, 1), 'CENTER'),
            ('ALIGN', (0, 2), (-1, 2), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, 1), 5),
        ]),
        radius=5,
        padding=6,
        color=colors.grey
    )
    elements.append(KeepTogether(qr_section))
    elements.append(Spacer(1, 0.35 * inch))

    # Surgery Contact
    surgery_title = safe_paragraph("<b>Surgery Contact Information</b>", styles['CustomTableTitleCenter'])
    centered_table_text = styles['CustomCenterTableTexttight'] 
    surgery_contact_data = [
        [surgery_title],
        [safe_paragraph(f"{surgery_info.get('surgery_name', 'Unknown Surgery')}", centered_table_text)],
        [safe_paragraph(f"{surgery_info.get('surgery_address_line1', 'N/A')}", centered_table_text)],
        [safe_paragraph(f"{surgery_info.get('surgery_address_line2', 'N/A')}" if surgery_info.get('surgery_address_line2') else "", centered_table_text)],
        [safe_paragraph(f"{surgery_info.get('surgery_city', 'N/A')}", centered_table_text)],
        [safe_paragraph(f"{surgery_info.get('surgery_postcode', 'N/A')}", centered_table_text)],
        [safe_paragraph(f"<font face='{font_name_bold}'>Tel:</font> {escape(surgery_info.get('surgery_phone', 'N/A'))}", centered_table_text)]
    ]
    surgery_contact_table = create_boxed_table(
        data=surgery_contact_data,
        widths=[doc.width - 5 * inch],
        style=TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('PADDING', (0, 0), (-1, -1), 4),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 10),
            ('SPLITBYROW', (0, 0), (-1, -1), True)
        ]),
        radius=5,
        padding=4,
        color=colors.grey
    )
    centered_surgery_contact_table = Table([[surgery_contact_table]], colWidths=[doc.width - 0.15 * inch], rowHeights=[None])
    centered_surgery_contact_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(centered_surgery_contact_table)
    elements.append(Spacer(1, 0.35 * inch))

    # Header and Footer
    def add_header_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(font_name, 10)
        canvas.setFillColor(colors.black)
        canvas.drawString(doc.leftMargin, doc.pagesize[1] - doc.topMargin + 20,
                          f"{surgery_info.get('surgery_name','Unknown Surgery')}")
        canvas.drawCentredString(doc.pagesize[0]/2, doc.pagesize[1] - doc.topMargin + 20,
                                 "Chronic Kidney Disease Review")
        canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, doc.pagesize[1] - doc.topMargin + 20,
                               f"Date: {datetime.now().strftime('%d-%m-%Y')}")
        canvas.line(doc.leftMargin, doc.pagesize[1] - doc.topMargin + 10,
                    doc.pagesize[0] - doc.rightMargin, doc.pagesize[1] - doc.topMargin + 10)

        canvas.setFont(font_name, 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(doc.leftMargin, doc.bottomMargin - 10,
                          f"Page {canvas.getPageNumber()}")  # was: doc.page
        canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, doc.bottomMargin - 10,
                               f"Tel: {surgery_info.get('surgery_phone','N/A')}")
        canvas.line(doc.leftMargin, doc.bottomMargin,
                    doc.pagesize[0] - doc.rightMargin, doc.bottomMargin)
        canvas.restoreState()

    doc.build(elements, onFirstPage=add_header_footer, onLaterPages=add_header_footer)
    logging.info(f"PDF generated successfully at {output_path}")

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
