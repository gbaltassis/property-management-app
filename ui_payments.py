import streamlit as st
import gsheets_service
import uuid
import pandas as pd
from datetime import date

def show():
    st.header("Καταγραφή Πληρωμών")
    st.caption("Καταχώρηση εισπράξεων (ενοίκια, λογαριασμοί) για πλήρη ιχνηλασιμότητα.")

    # Φόρτωση δεδομένων από τα Google Sheets
    try:
        leases_df = gsheets_service.fetch_all_leases()
        tenants_df = gsheets_service.fetch_all_tenants()
        properties_df = gsheets_service.fetch_all_properties()
    except Exception as e:
        st.error("Αδυναμία φόρτωσης δεδομένων. Ελέγξτε τη σύνδεση με το Google Sheet.")
        return

    # Έλεγχος αν υπάρχουν καταχωρημένες μισθώσεις
    if leases_df.empty:
        st.info("Δεν υπάρχουν ενεργές μισθώσεις στη βάση. Προσθέστε πρώτα μια μίσθωση για να καταγράψετε πληρωμή.")
        return

    # Προετοιμασία λίστας επιλογών για το Dropdown (Συνδυασμός Ονόματος + Διεύθυνσης)
    lease_options = {}
    for index, row in leases_df.iterrows():
        l_id = row.get("Lease_ID")
        t_id = row.get("Tenant_ID")
        p_id = row.get("Property_ID")
        
        # Εύρεση ονόματος ενοικιαστή
        tenant_name = "Άγνωστος Ενοικιαστής"
        if not tenants_df.empty and "Tenant_ID" in tenants_df.columns:
            t_match = tenants_df[tenants_df["Tenant_ID"] == t_id]
            if not t_match.empty:
                tenant_name = f"{t_match.iloc[0]['Όνομα']} {t_match.iloc[0]['Επώνυμο']}"
        
        # Εύρεση διεύθυνσης ακινήτου
        prop_address = "Άγνωστο Ακίνητο"
        if not properties_df.empty and "Property_ID" in properties_df.columns:
            p_match = properties_df[properties_df["Property_ID"] == p_id]
            if not p_match.empty:
                prop_address = f"{p_match.iloc[0]['Διεύθυνση']} {p_match.iloc[0]['Αριθμός']}"
                
        # Δημιουργία φιλικού κειμένου: π.χ. "Ιωάννης Παπαδόπουλος (Αριστοτέλους 15)"
        display_text = f"{tenant_name} ({prop_address})"
        lease_options[l_id] = display_text

    # Φόρμα καταχώρησης πληρωμής
    with st.form("new_payment_form", clear_on_submit=True):
        
        # Το selectbox δείχνει το φιλικό κείμενο, αλλά επιστρέφει το Lease_ID
        selected_lease_id = st.selectbox(
            "Επιλογή Μίσθωσης / Ενοικιαστή *", 
            options=list(lease_options.keys()),
            format_func=lambda x: lease_options[x]
        )
        
        col1, col2 = st.columns(2)
        with col1:
            payment_type = st.selectbox(
                "Είδος Οφειλής *", 
                ["Ενοίκιο", "Νερό", "Κοινόχρηστα", "Ρεύμα", "Άλλο"]
            )
        with col2:
            amount = st.number_input("Ποσό (€) *", min_value=0.0, step=10.0, format="%.2f")
            
        col3, col4 = st.columns(2)
        with col3:
            date_received = st.date_input("Ημερομηνία Είσπραξης *", value=date.today())
        with col4:
            bank_account = st.selectbox(
                "Τράπεζα / Τρόπος *", 
                ["Εθνική Τράπεζα", "Eurobank", "Alpha Bank", "Τράπεζα Πειραιώς", "Μετρητά", "Άλλο"]
            )

        submit_btn = st.form_submit_button("Αποθήκευση Είσπραξης", use_container_width=True)
        
        if submit_btn:
            if selected_lease_id and amount > 0:
                # Δημιουργία Payment_ID (π.χ. PAY-A1B2C3)
                pay_id = f"PAY-{uuid.uuid4().hex[:6].upper()}"
                date_str = date_received.strftime("%Y-%m-%d")
                
                # Σειρά στη Βάση: Payment_ID, Lease_ID, Payment_Type, Amount, Date_Received, Bank_Account
                row_data = [pay_id, selected_lease_id, payment_type, amount, date_str, bank_account]
                
                try:
                    gsheets_service.add_payment(row_data)
                    st.success(f"Η είσπραξη {amount}€ για '{payment_type}' καταχωρήθηκε επιτυχώς!")
                except Exception as e:
                    st.error(f"Σφάλμα αποθήκευσης: {e}")
            else:
                st.warning("Παρακαλώ εισάγετε έγκυρο ποσό μεγαλύτερο του μηδενός.")
