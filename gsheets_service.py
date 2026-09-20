import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# Το μοναδικό ID του Google Sheet "Property Management Database"
SHEET_ID = "1_X_yC1znPvJ3HtPA6X43_FWdabkPljfBb-IxLaHL_To"

@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    credentials_dict = dict(st.secrets["gcp_service_account"])
    credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    return gspread.authorize(credentials)

def get_worksheet(sheet_name):
    client = init_connection()
    spreadsheet = client.open_by_key(SHEET_ID)
    return spreadsheet.worksheet(sheet_name)

# --- Συναρτήσεις Ανάγνωσης Δεδομένων (ΑΛΛΑΓΗ σε get_all_values για προστασία του κόμματος) ---
@st.cache_data(ttl=300)
def fetch_all_properties():
    ws = get_worksheet("Properties")
    data = ws.get_all_values()
    if len(data) > 1: return pd.DataFrame(data[1:], columns=data[0])
    return pd.DataFrame(columns=data[0] if data else [])

@st.cache_data(ttl=300)
def fetch_all_tenants():
    ws = get_worksheet("Tenants")
    data = ws.get_all_values()
    if len(data) > 1: return pd.DataFrame(data[1:], columns=data[0])
    return pd.DataFrame(columns=data[0] if data else [])
    
@st.cache_data(ttl=300)
def fetch_all_leases():
    ws = get_worksheet("Leases")
    data = ws.get_all_values()
    if len(data) > 1: return pd.DataFrame(data[1:], columns=data[0])
    return pd.DataFrame(columns=data[0] if data else [])

@st.cache_data(ttl=300)
def fetch_all_payments():
    ws = get_worksheet("Payments")
    data = ws.get_all_values()
    if len(data) > 1: return pd.DataFrame(data[1:], columns=data[0])
    return pd.DataFrame(columns=data[0] if data else [])

# --- Συναρτήσεις Εγγραφής Δεδομένων ---
def add_property(property_data):
    ws = get_worksheet("Properties")
    ws.append_row(property_data)
    fetch_all_properties.clear()

def add_tenant(tenant_data):
    ws = get_worksheet("Tenants")
    ws.append_row(tenant_data)
    fetch_all_tenants.clear()
    
def add_lease(lease_data):
    ws = get_worksheet("Leases")
    ws.append_row(lease_data)
    fetch_all_leases.clear()
    
def add_payment(payment_data):
    ws = get_worksheet("Payments")
    ws.append_row(payment_data)
    fetch_all_payments.clear()

# --- Συναρτήσεις Επεξεργασίας & Διαγραφής ---
def update_property(property_id, new_data_row):
    ws = get_worksheet("Properties")
    try:
        cell = ws.find(property_id, in_column=1)
        for idx, val in enumerate(new_data_row):
            ws.update_cell(cell.row, idx + 1, val)
        fetch_all_properties.clear()
    except gspread.exceptions.CellNotFound:
        raise Exception(f"Δεν βρέθηκε ακίνητο με ID: {property_id}")

def delete_property(property_id):
    ws = get_worksheet("Properties")
    try:
        cell = ws.find(property_id, in_column=1)
        ws.delete_rows(cell.row)
        fetch_all_properties.clear()
    except gspread.exceptions.CellNotFound:
        raise Exception("Το ακίνητο δεν βρέθηκε για διαγραφή.")
