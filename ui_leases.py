import streamlit as st
import gsheets_service
import uuid
import pandas as pd
from datetime import date

def show():
    st.header("Νέα Μίσθωση")
    
    try:
        properties_df = gsheets_service.fetch_all_properties()
        tenants_df = gsheets_service.fetch_all_tenants()
    except:
        st.error("Σφάλμα σύνδεσης.")
        return

    if properties_df.empty or tenants_df.empty:
        st.warning("Πρέπει να καταχωρήσετε Ακίνητο και Ενοικιαστή στο Μητρώο.")
        return

    prop_options = {row["Property_ID"]: f"{row.get('Διεύθυνση','')} {row.get('Αριθμός','')} - {row.get('Χαρακτηριστικό', '')}" for _, row in properties_df.iterrows()}
    tenant_options = {row["Tenant_ID"]: f"{row['Όνομα']} {row['Επώνυμο']} (ΑΦΜ: {row['ΑΦΜ']})" for _, row in tenants_df.iterrows()}

    with st.form("new_lease_form", clear_on_submit=True):
        st.subheader("1. Αντιστοίχιση")
        selected_prop_id = st.selectbox("Ακίνητο *", options=list(prop_options.keys()), format_func=lambda x: prop_options[x])
        selected_tenant_id = st.selectbox("Ενοικιαστής *", options=list(tenant_options.keys()), format_func=lambda x: tenant_options[x])
        
        st.subheader("2. Οικονομικοί Όροι")
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Ημ/νία Έναρξης *", value=date.today())
            monthly_rent = st.number_input("Μηνιαίο Μίσθωμα (€) *", min_value=0.0, step=10.0, format="%.2f")
        with col2:
            end_date = st.date_input("Ημ/νία Λήξης *")
            
        special_agreements = st.text_area("Ειδικές Συμφωνίες")
        aade_url = st.text_input("Σύνδεσμος ΑΑΔΕ (URL)", placeholder="https://...")

        submit_lease = st.form_submit_button("Αποθήκευση Μίσθωσης", use_container_width=True)
        
        if submit_lease:
            if monthly_rent > 0 and end_date > start_date:
                lease_id = f"LS-{uuid.uuid4().hex[:6].upper()}"
                row_data = [
                    lease_id, selected_prop_id, selected_tenant_id, 
                    start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), 
                    monthly_rent, special_agreements, aade_url
                ]
                try:
                    gsheets_service.add_lease(row_data)
                    st.success("Η μίσθωση αποθηκεύτηκε!")
                except Exception as e:
                    st.error(f"Σφάλμα: {e}")
            else:
                st.warning("Ελέγξτε τις ημερομηνίες και το ποσό.")
