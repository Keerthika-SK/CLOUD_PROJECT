import streamlit as st
import re
import io
import httpx
from openai import AzureOpenAI
from PyPDF2 import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

# Azure OpenAI config - use YOUR KEY
ai_endpoint = "https://skee-mff5fbkc-eastus2.cognitiveservices.azure.com/"
ai_api_key = "F7UGRXFhkjG9JIsUm3s2FXx089ON7lBfruo87vCnJAEzR165MgCYJQQJ99BIACHYHv6XJ3w3AAAAACOGpbGy"
deployment_name = "Letter-generator"
ai_api_version = "2025-01-01-preview"
client = AzureOpenAI(api_version=ai_api_version, azure_endpoint=ai_endpoint, api_key=ai_api_key, timeout=httpx.Timeout(30.0))

certificate_template = '''

This is to certify that Mr./Ms. [Student Name], son/daughter of Mr./Mrs. [Parent's Name], is a bonafide student of Rajalakshmi Engineering College, Chennai, enrolled in the [Department Name] for the [Course Name] program during the academic year [Start Year] to [End Year].
He/She has completed/ is currently pursuing his/her studies in the [Year/Semester] of the course.
This certificate is issued to him/her on request for the purpose of [Purpose, e.g., Higher Studies, Bank Loan, Passport, etc.].
'''

def create_text_overlay_wrapped(text, x=45, y=660, width=520, height=180, font_size=16, line_spacing=10):
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=A4)
    styles = getSampleStyleSheet()
    style = ParagraphStyle(
        'custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=font_size,
        leading=font_size + line_spacing,
        alignment=4,  # Justified
    )
    para = Paragraph(text, style)
    frame = Frame(x, y - height, width, height, showBoundary=0)
    frame.addFromList([para], can)
    can.showPage()
    can.save()
    packet.seek(0)
    return packet

st.set_page_config(page_title="Bonafide Certificate Generator", layout="centered")
st.title("Bonafide Certificate PDF Editor (Pro)")

uploaded_pdf = st.file_uploader("Upload your official template PDF (with logo/header/footer)", type="pdf")

field_names = re.findall(r'\[([^\]]+)\]', certificate_template)
user_entries = {field: st.text_input(f"{field}") for field in field_names}

if st.button("Generate and Download Certificate"):
    if not uploaded_pdf:
        st.error("Please upload your template PDF.")
    elif not all(user_entries.values()):
        st.error("Please fill all certificate fields.")
    else:
        pairs = '\n'.join([f"{k}: {v}" for k, v in user_entries.items()])
        prompt = f"""Replace the brackets in the following certificate template with these values.

Template:
{certificate_template}

Field values:
{pairs}

Return ONLY the final certificate text formatted appropriately with all replacements."""

        with st.spinner("Generating certificate text..."):
            response = client.chat.completions.create(
                model=deployment_name,
                messages=[
                    {"role": "system", "content": "You are a document automation assistant."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=500,
                temperature=0,
            )
            bonafide_text = response.choices[0].message.content

        with st.spinner("Overlaying text onto PDF..."):
            packet = create_text_overlay_wrapped(
                bonafide_text,
                x=45,        # Left margin
                y=660,       # Distance from bottom to top of box (tune for your template)
                width=520,   # Width of text area (tune for your template!)
                height=180,  # Height of text area (increase if you need more body space)
                font_size=16,
                line_spacing=10
            )
            overlay_pdf = PdfReader(packet)
            template_pdf = PdfReader(uploaded_pdf)
            template_page = template_pdf.pages[0]
            if len(overlay_pdf.pages) == 0:
                st.error("Overlay PDF has no pages: Increase height or adjust coordinates.")
            else:
                template_page.merge_page(overlay_pdf.pages[0])
                writer = PdfWriter()
                writer.add_page(template_page)
                result_bytes = io.BytesIO()
                writer.write(result_bytes)
                result_bytes.seek(0)
                st.success("Download your completed certificate below.")
                st.download_button(
                    label="Download Certificate PDF",
                    data=result_bytes,
                    file_name="filled_bonafide_certificate.pdf",
                    mime="application/pdf"
                )
                st.subheader("Generated Certificate Text")
                st.text_area("", bonafide_text, height=300)
