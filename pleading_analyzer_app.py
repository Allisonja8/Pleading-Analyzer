import streamlit as st
import docx2txt
import pdfplumber
import spacy
from spacy.cli import download
import json
import csv
import tempfile
import re
from io import StringIO
import pytesseract
from PIL import Image

# Download and load the spaCy model
download("en_core_web_sm")
nlp = spacy.load("en_core_web_sm")

st.title("Court Pleading Analyzer")
st.write("Upload a court pleading (PDF or DOCX) to extract key legal information and named entities.")

uploaded_file = st.file_uploader("Choose a PDF or DOCX file", type=["pdf", "docx"])

patterns = {
    "case_number": r"(Case\s*No\.?\s*[:\s]*[\w\d\-\/]+)",
    "court_name": r"(In\s+the\s+\w+(\s+\w+)*\s+Court.*?)\n",
    "filing_date": r"(Filed\s*[:\s]*\w+\s+\d{1,2},\s+\d{4})",
    "pleading_type": r"(Complaint|Answer|Motion to Dismiss|Reply|Petition|Notice.*?)\n",
    "jurisdiction": r"(Jurisdiction.*?)\n",
    "attorney_info": r"(Attorney\s+for\s+.*?\n.*?\n.*?)\n",
}

def extract_text(file):
    if file.name.endswith(".pdf"):
        with pdfplumber.open(file) as pdf:
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
                else:
                    img = page.to_image(resolution=300).original
                    img_path = tempfile.mktemp(suffix=".png")
                    img.save(img_path)
                    text += pytesseract.image_to_string(Image.open(img_path)) + "\n"
            return text
    elif file.name.endswith(".docx"):
        return docx2txt.process(file)
    else:
        return ""

def extract_info(text):
    info = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        info[key] = match.group(1).strip() if match else None
    info["plaintiff"] = re.findall(r"Plaintiff[s]*:?\s*(.*?)\n", text, re.IGNORECASE)
    info["defendant"] = re.findall(r"Defendant[s]*:?\s*(.*?)\n", text, re.IGNORECASE)
    allegations = re.findall(r"(CAUSE OF ACTION.*?)\n\n", text, re.IGNORECASE | re.DOTALL)
    info["causes_of_action"] = allegations if allegations else None
    date_mentions = re.findall(r"(\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b)", text)
    info["incident_dates"] = date_mentions
    return info

def extract_named_entities(text):
    doc = nlp(text)
    entities = {}
    for ent in doc.ents:
        entities.setdefault(ent.label_, set()).add(ent.text)
    return {label: list(ents) for label, ents in entities.items()}

def to_csv(data_dict):
    output = StringIO()
    writer = csv.writer(output)
    for key, value in data_dict.items():
        writer.writerow([key, json.dumps(value) if isinstance(value, list) else value])
    return output.getvalue()

if uploaded_file:
    raw_text = extract_text(uploaded_file)
    if raw_text:
        st.subheader("Extracted Information")
        extracted_info = extract_info(raw_text)
        for k, v in extracted_info.items():
            st.write(f"**{k.replace('_', ' ').title()}**: {v}")

        st.subheader("Named Entities")
        entities = extract_named_entities(raw_text)
        for label, ents in entities.items():
            st.write(f"**{label}**: {', '.join(set(ents))}")

        st.download_button("Download as CSV", to_csv({**extracted_info, **entities}), file_name="extracted_info.csv")
        st.download_button("Download as JSON", json.dumps({**extracted_info, **entities}, indent=2), file_name="extracted_info.json")
    else:
        st.error("Could not extract text from file. Ensure it is not a scanned image.")
