import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

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

# --- Συναρτήσεις Ανάγνωσης Δεδομένων ---
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

@st.cache_data(ttl=300)
def fetch_all_expenses():
    ws = get_worksheet("Expenses")
    data = ws.get_all_values()
    if len(data) > 1: return pd.DataFrame(data[1:], columns=data[0])
    return pd.DataFrame(columns=data[0] if data else [])

# --- Συναρτήσεις Εγγραφής Δεδομένων ---
def add_property(data): get_worksheet("Properties").append_row(data); fetch_all_properties.clear()
def add_tenant(data): get_worksheet("Tenants").append_row(data); fetch_all_tenants.clear()
def add_lease(data): get_worksheet("Leases").append_row(data); fetch_all_leases.clear()
def add_payment(data): get_worksheet("Payments").append_row(data); fetch_all_payments.clear()
def add_expense(data): get_worksheet("Expenses").append_row(data); fetch_all_expenses.clear()

# --- Συναρτήσεις Επεξεργασίας & Διαγραφής (Batch Update) ---
def update_row_by_id(sheet_name, row_id, new_data_row, cache_func):
    ws = get_worksheet(sheet_name)
    try:
        cell = ws.find(row_id, in_column=1)
        cell_list = ws.range(cell.row, 1, cell.row, len(new_data_row))
        for i, val in enumerate(new_data_row): cell_list[i].value = str(val)
        ws.update_cells(cell_list)
        cache_func.clear()
    except Exception as e: raise Exception(f"Λεπτομέρειες: {e}")

def delete_row_by_id(sheet_name, row_id, cache_func):
    ws = get_worksheet(sheet_name)
    try:
        cell = ws.find(row_id, in_column=1)
        ws.delete_rows(cell.row)
        cache_func.clear()
    except Exception as e: raise Exception(f"Λεπτομέρειες: {e}")

def update_property(id, row): update_row_by_id("Properties", id, row, fetch_all_properties)
def delete_property(id): delete_row_by_id("Properties", id, fetch_all_properties)
def update_tenant(id, row): update_row_by_id("Tenants", id, row, fetch_all_tenants)
def delete_tenant(id): delete_row_by_id("Tenants", id, fetch_all_tenants)
def update_lease(id, row): update_row_by_id("Leases", id, row, fetch_all_leases)
def delete_lease(id): delete_row_by_id("Leases", id, fetch_all_leases)
def update_payment(id, row): update_row_by_id("Payments", id, row, fetch_all_payments)
def delete_payment(id): delete_row_by_id("Payments", id, fetch_all_payments)
def update_expense(id, row): update_row_by_id("Expenses", id, row, fetch_all_expenses)
def delete_expense(id): delete_row_by_id("Expenses", id, fetch_all_expenses)

def fetch_all_insurances():
    worksheet = get_worksheet("Insurances")
    if not worksheet: return pd.DataFrame()
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

def add_insurance(row_data):
    worksheet = get_worksheet("Insurances")
    worksheet.append_row(row_data)

def update_insurance(ins_id, row_data):
    worksheet = get_worksheet("Insurances")
    cell = worksheet.find(ins_id, in_column=1)
    if cell:
        worksheet.update(f"A{cell.row}:J{cell.row}", [row_data])

def delete_insurance(ins_id):
    worksheet = get_worksheet("Insurances")
    cell = worksheet.find(ins_id, in_column=1)
    if cell:
        worksheet.delete_rows(cell.row)

# --- NOTIFICATIONS LOG ---
def fetch_all_notifications():
    sheet = client.open(SPREADSHEET_NAME).worksheet("Notifications_Log")
    records = sheet.get_all_records()
    return pd.DataFrame(records)

def add_notification_log(row_data):
    sheet = client.open(SPREADSHEET_NAME).worksheet("Notifications_Log")
    sheet.append_row(row_data)

def fetch_all_owners():
    conn = st.connection("gsheets", type=GSheetsConnection)
    return conn.read(worksheet="Owners", usecols=list(range(6)))

def add_owner(row_data):
    conn = st.connection("gsheets", type=GSheetsConnection)
    conn.insert(worksheet="Owners", data=[row_data])

def update_owner(owner_id, new_row_data):
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(worksheet="Owners", usecols=list(range(6)))
    if not df.empty and 'Owner_ID' in df.columns:
        idx = df.index[df['Owner_ID'] == owner_id].tolist()
        if idx:
            conn.update(worksheet="Owners", data=[new_row_data], range=f"A{idx[0]+2}:F{idx[0]+2}")

def delete_owner(owner_id):
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(worksheet="Owners", usecols=list(range(6)))
    if not df.empty and 'Owner_ID' in df.columns:
        idx = df.index[df['Owner_ID'] == owner_id].tolist()
        if idx:
            blank_row = [owner_id, "ΔΙΑΓΡΑΜΜΕΝΟ", "-", "-", "-", "-"]
            conn.update(worksheet="Owners", data=[blank_row], range=f"A{idx[0]+2}:F{idx[0]+2}")
