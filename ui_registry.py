import streamlit as st
import gsheets_service
import uuid

def show():
    st.header("Μητρώο")
    st.caption("Καταχώρηση νέων ακινήτων και ενοικιαστών στη βάση δεδομένων.")
    tab_prop, tab_tenant = st.tabs(["🏠 Νέο Ακίνητο", "👤 Νέος Ενοικιαστής"])

    with tab_prop:
        with st.form("new_property_form", clear_on_submit=True):
            charact = st.text_input("Χαρακτηριστικό Ακινήτου (π.χ. Διαμέρισμα Κέντρο, Εξοχικό) *")
            atak = st.text_input("ΑΤΑΚ *")
            nomos = st.text_input("Νομός", value="Αττικής") 
            dimos = st.text_input("Περιοχή / Δήμος *")
            
            col1, col2 = st.columns(2)
            with col1:
                address = st.text_input("Οδός *")
            with col2:
                number = st.text_input("Αριθμός")
                
            col3, col4 = st.columns(2)
            with col3:
                floor = st.text_input("Όροφος (π.χ. 1ος, Ισόγειο)")
            with col4:
                sqm = st.number_input("Επιφάνεια (m2) *", min_value=0.0, step=1.0)
                
            submit_prop = st.form_submit_button("Αποθήκευση Ακινήτου", use_container_width=True)
            
            if submit_prop:
                if charact and atak and dimos and address and sqm > 0:
                    prop_id = f"PR-{uuid.uuid4().hex[:6].upper()}"
                    # Προσθήκη του χαρακτηριστικού στο τέλος της λίστας
                    row_data = [prop_id, atak, nomos, dimos, address, number, floor, sqm, charact]
                    try:
                        gsheets_service.add_property(row_data)
                        st.success(f"Το ακίνητο αποθηκεύτηκε επιτυχώς!")
                    except Exception as e:
                        st.error(f"Σφάλμα: {e}")
                else:
                    st.warning("Παρακαλώ συμπληρώστε τα υποχρεωτικά πεδία (*).")

    with tab_tenant:
        with st.form("new_tenant_form", clear_on_submit=True):
            fname = st.text_input("Όνομα *")
            lname = st.text_input("Επώνυμο *")
            afm = st.text_input("ΑΦΜ *")
            submit_tenant = st.form_submit_button("Αποθήκευση Ενοικιαστή", use_container_width=True)
            
            if submit_tenant:
                if fname and lname and afm:
                    tenant_id = f"TN-{uuid.uuid4().hex[:6].upper()}"
                    row_data = [tenant_id, fname, lname, afm]
                    try:
                        gsheets_service.add_tenant(row_data)
                        st.success(f"Ο ενοικιαστής αποθηκεύτηκε επιτυχώς!")
                    except Exception as e:
                        st.error(f"Σφάλμα: {e}")
                else:
                    st.warning("Παρακαλώ συμπληρώστε όλα τα πεδία.")
