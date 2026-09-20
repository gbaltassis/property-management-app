import streamlit as st
import gsheets_service
import uuid

def show():
    st.header("Μητρώο")
    st.caption("Καταχώρηση νέων ακινήτων και ενοικιαστών στη βάση δεδομένων.")

    # Χωρίζουμε την οθόνη σε 2 υπο-καρτέλες για οικονομία χώρου στο κινητό
    tab_prop, tab_tenant = st.tabs(["🏠 Νέο Ακίνητο", "👤 Νέος Ενοικιαστής"])

    # --- ΦΟΡΜΑ ΝΕΟΥ ΑΚΙΝΗΤΟΥ ---
    with tab_prop:
        # Το clear_on_submit καθαρίζει τα πεδία μόλις πατηθεί η αποθήκευση
        with st.form("new_property_form", clear_on_submit=True):
            atak = st.text_input("ΑΤΑΚ *")
            nomos = st.text_input("Νομός", value="Αττικής") 
            dimos = st.text_input("Περιοχή / Δήμος *")
            
            # Βάζουμε κάποια πεδία δίπλα-δίπλα (στο κινητό το Streamlit τα βάζει αυτόματα το ένα κάτω από το άλλο)
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
                
            # Full-width κουμπί για εύκολο πάτημα στο κινητό
            submit_prop = st.form_submit_button("Αποθήκευση Ακινήτου", use_container_width=True)
            
            if submit_prop:
                if atak and dimos and address and sqm > 0:
                    # Δημιουργία ενός μοναδικού ID για το ακίνητο
                    prop_id = f"PR-{uuid.uuid4().hex[:6].upper()}"
                    
                    # Σειρά στη Βάση: Property_ID, ΑΤΑΚ, Νομός, Περιοχή/Δήμος, Διεύθυνση, Αριθμός, Όροφος, Επιφάνεια m2
                    row_data = [prop_id, atak, nomos, dimos, address, number, floor, sqm]
                    
                    try:
                        gsheets_service.add_property(row_data)
                        st.success(f"Το ακίνητο αποθηκεύτηκε επιτυχώς!")
                    except Exception as e:
                        st.error(f"Σφάλμα κατά την αποθήκευση: {e}")
                else:
                    st.warning("Παρακαλώ συμπληρώστε τα υποχρεωτικά πεδία (*).")

    # --- ΦΟΡΜΑ ΝΕΟΥ ΕΝΟΙΚΙΑΣΤΗ ---
    with tab_tenant:
        with st.form("new_tenant_form", clear_on_submit=True):
            fname = st.text_input("Όνομα *")
            lname = st.text_input("Επώνυμο *")
            afm = st.text_input("ΑΦΜ *")
            
            submit_tenant = st.form_submit_button("Αποθήκευση Ενοικιαστή", use_container_width=True)
            
            if submit_tenant:
                if fname and lname and afm:
                    # Δημιουργία ενός μοναδικού ID για τον ενοικιαστή
                    tenant_id = f"TN-{uuid.uuid4().hex[:6].upper()}"
                    
                    # Σειρά στη Βάση: Tenant_ID, Όνομα, Επώνυμο, ΑΦΜ
                    row_data = [tenant_id, fname, lname, afm]
                    
                    try:
                        gsheets_service.add_tenant(row_data)
                        st.success(f"Ο ενοικιαστής αποθηκεύτηκε επιτυχώς!")
                    except Exception as e:
                        st.error(f"Σφάλμα κατά την αποθήκευση: {e}")
                else:
                    st.warning("Παρακαλώ συμπληρώστε όλα τα πεδία.")
