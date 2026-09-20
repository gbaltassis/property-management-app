import streamlit as st
import gsheets_service
import uuid
import pandas as pd
from datetime import date

def show():
    st.header("Νέα Μίσθωση")
    st.caption("Σύνδεση ακινήτου με ενοικιαστή και ορισμός όρων.")

    # Φόρτωση λιστών από τη βάση
    try:
        properties_df = gsheets_service.fetch_all_properties()
        tenants_df = gsheets_service.fetch_all_tenants()
    except Exception as e:
        st.error("Σφάλμα σύνδεσης με τη βάση δεδομένων.")
        return

    if properties_df.empty or tenants_df.empty:
        st.warning("Πρέπει να καταχωρήσετε τουλάχιστον ένα Ακίνητο και έναν Ενοικιαστή στο 'Μητρώο' για να δημιουργήσετε μίσθωση.")
        return

    # Προετοιμασία επιλογών
    prop_options = {row["Property_ID"]: f"{row['Διεύθυνση']} {row['Αριθμός']}, {row['Περιοχή/Δήμος']} ({row['ΑΤΑΚ']})" for _, row in properties_df.iterrows()}
    tenant_options = {row["Tenant_ID"]: f"{row['Όνομα']} {row['Επώνυμο']} (ΑΦΜ: {row['ΑΦΜ']})" for _, row in tenants_df.iterrows()}

    with st.form("new_lease_form", clear_on_submit=True):
        
        # --- 1. Βασικά Στοιχεία ---
        st.subheader("1. Αντιστοίχιση")
        selected_prop_id = st.selectbox("Ακίνητο *", options=list(prop_options.keys()), format_func=lambda x: prop_options[x])
        selected_tenant_id = st.selectbox("Ενοικιαστής *", options=list(tenant_options.keys()), format_func=lambda x: tenant_options[x])
        
        # --- 2. Στοιχεία Ιδιοκτήτη / Δικαιώματος ---
        st.subheader("2. Δικαίωμα Εκμετάλλευσης")
        col1, col2 = st.columns(2)
        with col1:
            owner_name = st.text_input("Όνομα Ιδιοκτήτη *", value="Γιώργος")
            owner_afm = st.text_input("ΑΦΜ Ιδιοκτήτη *")
        with col2:
            owner_surname = st.text_input("Επώνυμο Ιδιοκτήτη *", value="Μπαλτάσης")
            ownership_perc = st.number_input("Ποσοστό Ιδιοκτησίας (%)", min_value=1, max_value=100, value=100)
            
        right_type = st.selectbox("Είδος Εμπράγματου Δικαιώματος *", ["Πλήρης Κυριότητα", "Επικαρπία", "Ψιλή Κυριότητα"])
        
        # --- 3. Όροι Μίσθωσης ---
        st.subheader("3. Οικονομικοί Όροι & Διάρκεια")
        col3, col4 = st.columns(2)
        with col3:
            start_date = st.date_input("Ημ/νία Έναρξης *", value=date.today())
            monthly_rent = st.number_input("Μηνιαίο Μίσθωμα (€) *", min_value=0.0, step=10.0, format="%.2f")
        with col4:
            end_date = st.date_input("Ημ/νία Λήξης *")
            
        special_agreements = st.text_area("Ειδικές Συμφωνίες (π.χ. Κατοικίδια, Κοινόχρηστα, Νερό)")
        
        # --- 4. Έγγραφο ΑΑΔΕ (Τροποποιημένο σε URL) ---
        st.subheader("4. Αρχείο ΑΑΔΕ (Προαιρετικό)")
        aade_url = st.text_input("Επικόλληση Συνδέσμου (URL) από τη Δήλωση ΑΑΔΕ", placeholder="https://...")

        submit_lease = st.form_submit_button("Αποθήκευση Μίσθωσης", use_container_width=True)
        
        if submit_lease:
            if owner_name and owner_surname and owner_afm and monthly_rent > 0 and end_date > start_date:
                # 1. Δημιουργία ID Μίσθωσης
                lease_id = f"LS-{uuid.uuid4().hex[:6].upper()}"
                
                # 2. Εγγραφή στο Google Sheet
                # Σειρά: Lease_ID, Property_ID, Tenant_ID, Owner_Name, Owner_Surname, Owner_AFM, 
                # Ownership_Percentage, Property_Right_Type, Start_Date, End_Date, Monthly_Rent, Special_Agreements, AADE_Document_URL
                row_data = [
                    lease_id, selected_prop_id, selected_tenant_id, 
                    owner_name, owner_surname, owner_afm, 
                    ownership_perc, right_type, 
                    start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), 
                    monthly_rent, special_agreements, aade_url
                ]
                
                try:
                    gsheets_service.add_lease(row_data)
                    st.success("Η μίσθωση αποθηκεύτηκε επιτυχώς!")
                except Exception as e:
                    st.error(f"Σφάλμα αποθήκευσης στη βάση: {e}")
            else:
                st.warning("Ελέγξτε ότι τα υποχρεωτικά πεδία είναι συμπληρωμένα και η ημερομηνία λήξης είναι μετά την έναρξη.")
