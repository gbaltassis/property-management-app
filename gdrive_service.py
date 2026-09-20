import streamlit as st
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io

# Το ID του φακέλου "AADE Lease Agreements" στο Google Drive σου
FOLDER_ID = "1O9PP-jhr-GWbZANBaxxmYcT4nZxD4bFG"

@st.cache_resource
def init_drive_service():
    """Δημιουργεί τη σύνδεση με το Google Drive API."""
    scopes = ["https://www.googleapis.com/auth/drive"]
    
    # Χρησιμοποιούμε τα ίδια Secrets που βάλαμε για τα Sheets
    credentials_dict = dict(st.secrets["gcp_service_account"])
    credentials = Credentials.from_service_account_info(
        credentials_dict, 
        scopes=scopes
    )
    
    # Επιστρέφει την υπηρεσία (service) έτοιμη για εντολές
    return build('drive', 'v3', credentials=credentials)

def upload_aade_pdf(uploaded_file, filename):
    """
    Ανεβάζει το PDF (από το st.file_uploader) στο Google Drive, 
    του δίνει δικαιώματα ανάγνωσης και επιστρέφει το URL.
    """
    service = init_drive_service()
    
    # 1. Προετοιμασία των μεταδεδομένων του αρχείου (Όνομα και Πού θα αποθηκευτεί)
    file_metadata = {
        'name': filename,
        'parents': [FOLDER_ID]
    }
    
    # 2. Προετοιμασία του ίδιου του αρχείου για μεταφόρτωση
    media = MediaIoBaseUpload(
        io.BytesIO(uploaded_file.getvalue()), 
        mimetype='application/pdf',
        resumable=True
    )
    
    # 3. Εκτέλεση της μεταφόρτωσης
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()
    
    file_id = file.get('id')
    file_link = file.get('webViewLink')
    
    # 4. Αλλαγή δικαιωμάτων ώστε οποιοσδήποτε έχει το link να μπορεί να δει το PDF
    # (Χρήσιμο αν θέλεις να το δει ο ενοικιαστής ή η μητέρα σου)
    permission = {
        'type': 'anyone',
        'role': 'reader',
    }
    service.permissions().create(
        fileId=file_id,
        body=permission,
        fields='id'
    ).execute()
    
    # Επιστρέφουμε το URL για να το αποθηκεύσει το ui_leases.py στο Google Sheet
    return file_link
