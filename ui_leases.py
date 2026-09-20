import streamlit as st
import gsheets_service
import uuid
from datetime import date

def show():
    st.header("Νέα Μίσθωση")
    st.caption("Σύνδεση ακινήτου με ενοικιαστή και ορισμός πολλαπλών δικαιωμάτων.")

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
        
        st.subheader("2. Ιδιοκτήτες & Δικαιώματα")
        st.caption("Καταχωρήστε έως 3 δικαιώματα (π.χ. Ιδιοκτ. 1: 21.5% Ψιλή, Ιδιοκτ. 2: 78.5% Ψιλή, Ιδιοκτ. 2: 100% Επικαρπία).")
        
        owner_data = []
        for i in range(1, 4):
            with st.expander(f"Εγγραφή Δικαιώματος {i}" + (" (Υποχρεωτικό)" if i==1 else " (Προαιρετικό)"), expanded=(i==1)):
                c1, c2 = st.columns(2)
                n = c1.text_input(f"Όνομα", key=f"n{i}", value="Γιώργος" if i==1 else "")
                s = c2.text_input(f"Επώνυμο", key=f"s{i}", value="Μπαλτάσης" if i==1 else "")
                c3, c4, c5 = st.columns(3)
                afm = c3.text_input(f"ΑΦΜ", key=f"afm{i}")
                right = c4.selectbox(f"Είδος", ["Πλήρης Κυριότητα", "Επικαρπία", "Ψιλή Κυριότητα"], key=f"r{i}")
                perc = c5.number_input(f"Ποσοστό %", min_value=0.0, max_value=100.0, value=100.0 if i==1 else 0.0, step=1.0, key=f"p{i}")
                owner_data.extend([n, s, afm, right, perc])
        
        st.subheader("3. Οικονομικοί Όροι")
        col3, col4 = st.columns(2)
        with col3:
            start_date = st.date_input("Ημ/νία Έναρξης *", value=date.today())
            monthly_rent = st.number_input("Μηνιαίο Μίσθωμα (€) *", min_value=0.0, step=10.0, format="%.2f")
        with col4:
            end_date = st.date_input("Ημ/νία Λήξης *")
            
        special_agreements = st.text_area("Ειδικές Συμφωνίες")
        aade_url = st.text_input("Σύνδεσμος ΑΑΔΕ (URL)", placeholder="https://...")

        submit_lease = st.form_submit_button("Αποθήκευση Μίσθωσης", use_container_width=True)
        
        if submit_lease:
            if monthly_rent > 0 and end_date > start_date and owner_data[0]:
                lease_id = f"LS-{uuid.uuid4().hex[:6].upper()}"
                row_data = [lease_id, selected_prop_id, selected_tenant_id] + owner_data + [
                    start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), 
                    monthly_rent, special_agreements, aade_url
                ]
                try:
                    gsheets_service.add_lease(row_data)
                    st.success("Η μίσθωση αποθηκεύτηκε!")
                except Exception as e:
                    st.error(f"Σφάλμα: {e}")
            else:
                st.warning("Ελέγξτε ημερομηνίες, ποσό και τουλάχιστον τον 1ο ιδιοκτήτη.")
