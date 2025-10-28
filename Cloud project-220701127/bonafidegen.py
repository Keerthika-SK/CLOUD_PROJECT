import streamlit as st
import re
import io
import base64
import httpx
from openai import AzureOpenAI
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from PyPDF2 import PdfReader, PdfWriter
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

# Azure OpenAI config
ai_endpoint = "https://skee-mff5fbkc-eastus2.cognitiveservices.azure.com/"
ai_api_key = "F7UGRXFhkjG9JIsUm3s2FXx089ON7lBfruo87vCnJAEzR165MgCYJQQJ99BIACHYHv6XJ3w3AAAAACOGpbGy"
deployment_name = "Letter-generator"
ai_api_version = "2025-01-01-preview"
client = AzureOpenAI(
    api_version=ai_api_version,
    azure_endpoint=ai_endpoint,
    api_key=ai_api_key,
    timeout=httpx.Timeout(30.0),
)

# Azure Document Intelligence config
doc_endpoint = "https://documentverifier.cognitiveservices.azure.com/"
doc_api_key = "LFiuyHgu5btJnQkmoWybnX3JEa1tgRBbs9jMbgpicvpmoVC7EPrHJQQJ99BIACGhslBXJ3w3AAALACOGMc9l"
doc_client = DocumentAnalysisClient(endpoint=doc_endpoint, credential=AzureKeyCredential(doc_api_key))

certificate_template = '''
This is to certify that Mr./Ms. [Student Name], son/daughter of Mr./Mrs. [Parent's Name], is a bonafide student of Rajalakshmi Engineering College, Chennai, enrolled in the [Department Name] for the [Course Name] program during the academic year [Start Year] to [End Year].
He/She has completed/ is currently pursuing his/her studies in the [Year/Semester] of the course.
This certificate is issued to him/her on request for the purpose of [Purpose, e.g., Higher Studies, Bank Loan, Passport, etc.].
'''

def show_steps(step):
    steps = [
        ("1", "Input Details"),
        ("2", "Generate Letter"),
        ("3", "Preview Letter"),
        ("4", "Upload & Verify Document"),
        ("5", "Admin Approval"),
        ("6", "Preview & Download"),
    ]
    parts = []
    for i, (num, text) in enumerate(steps):
        if step > i:
            style = ("background:#11c26d;color:#fff;border-radius:15px;padding:4px 10px;margin-right:10px;")
            parts.append(f'<span style="{style}">&#10003; {text}</span>')
        elif step == i:
            style = ("border:2px solid #11c26d;border-radius:10px;padding:3px 8px;"
                "background:#e5ffe7;color:#11c26d;font-weight:bold;margin-right:10px;")
            parts.append(f'<span style="{style}">{num}. {text}</span>')
        else:
            style = ("color:#888;border-radius:10px;border:1.5px #ddd solid;padding:2px 8px;margin-right:10px;")
            parts.append(f'<span style="{style}">{num}. {text}</span>')
    st.markdown("<div style='display:flex; gap:10px;'>" + "".join(parts) + "</div><br/>", unsafe_allow_html=True)

def create_text_overlay(text, x=45, y=660, width=520, height=180, font_size=16, line_spacing=10):
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=A4)
    style = ParagraphStyle(
        'custom',
        fontName='Helvetica',
        fontSize=font_size,
        leading=font_size + line_spacing,
        alignment=4
    )
    para = Paragraph(text, style)
    frame = Frame(x, y - height, width, height, showBoundary=0)
    frame.addFromList([para], can)
    can.save()
    packet.seek(0)
    return packet

def extract_text(uploaded_file):
    poller = doc_client.begin_analyze_document(
        "prebuilt-document", document=uploaded_file)
    result = poller.result()
    text = " ".join(line.content for page in result.pages for line in page.lines)
    return text

def verify_fields(extracted_text, expected_name, expected_rollno):
    name_ok = expected_name.lower() in extracted_text.lower()
    roll_no_ok = expected_rollno.lower() in extracted_text.lower()
    college_ok = "rajalakshmi engineering college" in extracted_text.lower()
    return name_ok, roll_no_ok, college_ok

def pdf_viewer(pdf_bytes, height=650):
    b64 = base64.b64encode(pdf_bytes).decode()
    iframe = f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="{height}px" type="application/pdf"></iframe>'
    st.markdown(iframe, unsafe_allow_html=True)

st.set_page_config(page_title="Bonafide Certificate Generator", layout="centered")
if "step" not in st.session_state:
    st.session_state.step = 0

# Step 0: Input Details
if st.session_state.step == 0:
    show_steps(0)
    st.title("Enter Bonafide Certificate Details")
    fields = re.findall(r"\[([^\]]+)\]", certificate_template)
    entries = {}
    for f in fields:
        entries[f] = st.text_input(f, key=f)
    # Add Reg No input if not in template fields
    if "Reg No" not in entries:
        entries["Reg No"] = st.text_input("Reg No")
    st.session_state.entries = entries

    if st.button("Generate Letter"):
        if all(entries.values()):
            # Build detailed prompt with all entries
            prompt = f"""Write a formal Bonafide Certificate request letter with following details:
Student Name: {entries.get('Student Name', '')}
Parent's Name: {entries.get("Parent's Name", '')}
Department Name: {entries.get('Department Name', '')}
Course Name: {entries.get('Course Name', '')}
Start Year: {entries.get('Start Year', '')}
End Year: {entries.get('End Year', '')}
Year/Semester: {entries.get('Year/Semester', '')}
Purpose: {entries.get('Purpose', '')}

Address the letter to the principal of Rajalakshmi Engineering College."""

            with st.spinner("Generating letter..."):
                response = client.chat.completions.create(
                    model=deployment_name,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=512,
                    temperature=0.7,
                )
                letter_text = response.choices[0].message.content
            st.session_state.letter_text = letter_text
            st.session_state.step = 1
        else:
            st.error("Please fill all the fields.")

# Step 1: Edit and preview generated letter
elif st.session_state.step == 1:
    show_steps(1)
    st.header("Edit Generated Letter")
    edited_letter = st.text_area("Edit your letter:", value=st.session_state.letter_text, height=300)
    st.session_state.letter_text = edited_letter
    if st.button("Preview Letter"):
        if edited_letter.strip():
            st.session_state.step = 2
        else:
            st.error("Letter cannot be empty.")

# Step 2: Preview letter
elif st.session_state.step == 2:
    show_steps(2)
    st.header("Preview Letter")
    st.write(st.session_state.letter_text)
    if st.button("Next: Upload Verification Document"):
        st.session_state.step = 3

# Step 3: Upload document & verify
elif st.session_state.step == 3:
    show_steps(3)
    st.header("Upload Supporting Document for Verification")
    doc = st.file_uploader("Upload Document (PDF, JPG, PNG)", type=["pdf", "jpg", "jpeg", "png"])
    if doc:
        with st.spinner("Verifying document..."):
            try:
                text = extract_text(doc)
                entries = st.session_state.entries
                name_ok, roll_no_ok, college_ok = verify_fields(
                    text,
                    entries.get("Student Name", ""),
                    entries.get("Reg No", ""),
                )
            except Exception as e:
                st.error(f"Document verification failed: {e}")
                name_ok = roll_no_ok = college_ok = False

        if name_ok and roll_no_ok and college_ok:
            st.success("Verification successful: Name, Roll No, and College verified.")
            if st.button("Next: Admin Approval"):
                st.session_state.step = 4
        else:
            st.error(
                "Verification failed. Ensure Name, Roll Number, and 'Rajalakshmi Engineering College' are present in document."
            )

# Step 4: Admin approval (demo auto-approve)
elif st.session_state.step == 4:
    show_steps(4)
    st.header("Admin Approval")
    st.info("Request auto-approved for demo.")
    if st.button("Next: Certificate Preview & Download"):
        st.session_state.step = 5

# Step 5: Certificate preview and download
elif st.session_state.step == 5:
    show_steps(5)
    st.header("Certificate Preview & Download")
    try:
        with open("template.pdf", "rb") as f:
            template_pdf_bytes = f.read()
        template_stream = io.BytesIO(template_pdf_bytes)
        template_pdf = PdfReader(template_stream)
        pairs = "\n".join(f"{k}: {v}" for k, v in st.session_state.entries.items())
        prompt = f"""Replace the brackets in the following certificate template with these values.
Template:
{certificate_template}
Field values:
{pairs}
Return ONLY the final certificate text formatted appropriately with all replacements."""
        with st.spinner("Generating certificate text..."):
            resp = client.chat.completions.create(
                model=deployment_name,
                messages=[
                    {"role": "system", "content": "You are a document automation assistant."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=500,
                temperature=0,
            )
            cert_text = resp.choices[0].message.content

        packet = create_text_overlay(cert_text)
        overlay_pdf = PdfReader(packet)
        template_page = template_pdf.pages[0]
        template_page.merge_page(overlay_pdf.pages[0])
        writer = PdfWriter()
        writer.add_page(template_page)
        out_bytes = io.BytesIO()
        writer.write(out_bytes)
        out_bytes.seek(0)

        st.markdown('<span style="font-size:1.5em">👁 <b>Preview Certificate</b></span>', unsafe_allow_html=True)
        pdf_viewer(out_bytes.read())

        st.download_button("Download Certificate PDF", out_bytes.getvalue(), "bonafide_certificate.pdf", "application/pdf")
        st.text_area("Certificate Text", cert_text, height=300)

    except FileNotFoundError:
        st.error("Certificate template file template.pdf not found in the current folder.")
