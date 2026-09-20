import streamlit as st
import gsheets_service
import pandas as pd
import uuid

def show():
    st.header("Μητρώο")
    st.caption("Διαχείριση και επισκόπηση του χαρτοφυλακίου ακινήτων και του πελατολογίου.")

    # Φόρτωση δεδομένων για τις λίστες
    try:
        properties_df = gsheets_service.fetch_all_properties()
        tenants_df = gsheets_service.fetch_all_tenants()
        leases_df = gsheets_service.fetch_all_leases()
    except Exception as e:
        st.error("Σφάλμα κατά τη φόρτωση των δεδομένων από το Google Sheet.")
        return

    # Δημιουργία 4 καρτελών
    tab_prop_list, tab_tenant_list, tab_prop_new, tab_tenant_new = st.tabs([
        "🏢 Ακίνητα", 
        "👥 Ενοικιαστές", 
        "➕ Νέο Ακίνητο", 
        "➕ Νέος Ενοικ."
    ])

    # --- ΚΑΡΤΕΛΑ 1: ΛΙΣΤΑ ΑΚΙΝΗΤΩΝ ---
    with tab_prop_list:
        st.subheader("Καταχωρημένα Ακίνητα")
        
        if properties_df.empty:
            st.info("Δεν υπάρχουν καταχωρημένα ακίνητα.")
        else:
            prop_data = []
            for _, prop in properties_df.iterrows():
                p_id = prop.get("Property_ID")
                
                # Αναζήτηση των ιδιοκτητών (από την τελευταία/ενεργή μίσθωση για αυτό το ακίνητο)
                owners_info = "Μη ορισμένο (Δεν υπάρχει μίσθωση)"
                if not leases_df.empty:
                    # Βρίσκουμε τις μισθώσεις για αυτό το ακίνητο
                    prop_leases = leases_df[leases_df["Property_ID"] == p_id]
                    if not prop_leases.empty:
                        # Παίρνουμε την πιο πρόσφατη καταχώρηση
                        latest_lease = prop_leases.iloc[-1]
                        
                        owners_list = []
                        for i in range(1, 4):
                            n = latest_lease.get(f'Name_{i}', '')
                            s = latest_lease.get(f'Surname_{i}', '')
                            r = latest_lease.get(f'Right_{i}', '')
                            p = latest_lease.get(f'Perc_{i}', 0)
                            if str(n).strip() and float(p) > 0:
                                owners_list.append(f"{n} {s} ({r} {p}%)")
                        
                        if owners_list:
                            owners_info = " | ".join(owners_list)

                prop_data.append({
                    "Χαρακτηριστικό": prop.get("Χαρακτηριστικό", "-"),
                    "Διεύθυνση": f"{prop.get('Διεύθυνση', '')} {prop.get('Αριθμός', '')}",
                    "Περιοχή / Δήμος": prop.get("Περιοχή/Δήμος", ""),
                    "Επιφάνεια (m2)": prop.get("Επιφάνεια m2", ""),
                    "ΑΤΑΚ": prop.get("ΑΤΑΚ", ""),
                    "Ιδιοκτήτες / Δικαιώματα (Ενεργά)": owners_info
                })
            
            st.dataframe(pd.DataFrame(prop_data), use_container_width=True, hide_index=True)

    # --- ΚΑΡΤΕΛΑ 2: ΛΙΣΤΑ ΕΝΟΙΚΙΑΣΤΩΝ ---
    with tab_tenant_list:
        st.subheader("Μητρώο Ενοικιαστών")
        
        if tenants_df.empty:
            st.info("Δεν υπάρχουν καταχωρημένοι ενοικιαστές.")
        else:
            tenant_data = []
            for _, tenant in tenants_df.iterrows():
                tenant_data.append({
                    "Επώνυμο": tenant.get("Επώνυμο", ""),
                    "Όνομα": tenant.get("Όνομα", ""),
                    "ΑΦΜ": tenant.get("ΑΦΜ", "")
                })
            st.dataframe(pd.DataFrame(tenant_data), use_container_width=True, hide_index=True)

    # --- ΚΑΡΤΕΛΑ 3: ΦΟΡΜΑ ΝΕΟΥ ΑΚΙΝΗΤΟΥ ---
    with tab_prop_new:
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
                    row_data = [prop_id, atak, nomos, dimos, address, number, floor, sqm, charact]
                    try:
                        gsheets_service.add_property(row_data)
                        st.success(f"Το ακίνητο αποθηκεύτηκε επιτυχώς!")
                        # Προσθήκη κενού χώρου για ομαλή εμφάνιση
                        st.write("") 
                        st.info("ℹ️ Κάντε ανανέωση (Refresh) τη σελίδα για να δείτε τη νέα εγγραφή στη λίστα 'Ακίνητα'.")
                    except Exception as e:
                        st.error(f"Σφάλμα: {e}")
                else:
                    st.warning("Παρακαλώ συμπληρώστε τα υποχρεωτικά πεδία (*).")

    # --- ΚΑΡΤΕΛΑ 4: ΦΟΡΜΑ ΝΕΟΥ ΕΝΟΙΚΙΑΣΤΗ ---
    with tab_tenant_new:
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
                        st.write("")
                        st.info("ℹ️ Κάντε ανανέωση (Refresh) τη σελίδα για να δείτε τη νέα εγγραφή στη λίστα 'Ενοικιαστές'.")
                    except Exception as e:
                        st.error(f"Σφάλμα: {e}")
                else:
                    st.warning("Παρακαλώ συμπληρώστε όλα τα πεδία.")
