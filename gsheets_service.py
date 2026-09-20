import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# Το μοναδικό ID του Google Sheet "Property Management Database"
SHEET_ID = "1_X_yC1znPvJ3HtPA6X43_FWdabkPljfBb-IxLaHL_To"

@st.cache_resource
def init_connection():
    """Δημιουργεί τη σύνδεση με το Google Sheets χρησιμοποιώντας τα Secrets του Streamlit."""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # Διαβάζει τους κωδικούς που περάσαμε στα Advanced Settings του Streamlit
    credentials_dict = dict(st.secrets["gcp_service_account"])
    credentials = Credentials.from_service_account_info(
        credentials_dict, 
        scopes=scopes
    )
    
    return gspread.authorize(credentials)

def get_worksheet(sheet_name):
    """Επιστρέφει ένα συγκεκριμένο φύλλο εργασίας (tab) από το Google Sheet με βάση το όνομά του."""
    client = init_connection()
    spreadsheet = client.open_by_key(SHEET_ID)
    return spreadsheet.worksheet(sheet_name)

# --- Συναρτήσεις Ανάγνωσης Δεδομένων ---

# Προσθέτουμε @st.cache_data με ttl=300 (5 λεπτά)
# Αυτό σημαίνει ότι αν ζητήσεις τα δεδομένα 10 φορές μέσα σε 5 λεπτά, 
# θα ρωτήσει τη Google μόνο την πρώτη φορά.

@st.cache_data(ttl=300)
def fetch_all_properties():
    ws = get_worksheet("Properties")
    return pd.DataFrame(ws.get_all_records())

@st.cache_data(ttl=300)
def fetch_all_tenants():
    ws = get_worksheet("Tenants")
    return pd.DataFrame(ws.get_all_records())
    
@st.cache_data(ttl=300)
def fetch_all_leases():
    ws = get_worksheet("Leases")
    return pd.DataFrame(ws.get_all_records())

@st.cache_data(ttl=300)
def fetch_all_payments():
    ws = get_worksheet("Payments")
    return pd.DataFrame(ws.get_all_records())

# --- Συναρτήσεις Εγγραφής Δεδομένων ---

def add_property(property_data):
    ws = get_worksheet("Properties")
    ws.append_row(property_data)
    fetch_all_properties.clear() # Καθαρίζει τη μνήμη για να διαβάσει το νέο ακίνητο

def add_tenant(tenant_data):
    ws = get_worksheet("Tenants")
    ws.append_row(tenant_data)
    fetch_all_tenants.clear() # Καθαρίζει τη μνήμη
    
def add_lease(lease_data):
    ws = get_worksheet("Leases")
    ws.append_row(lease_data)
    fetch_all_leases.clear() # Καθαρίζει τη μνήμη
    
def add_payment(payment_data):
    ws = get_worksheet("Payments")
    ws.append_row(payment_data)
    fetch_all_payments.clear() # Καθαρίζει τη μνήμη
