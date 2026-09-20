import streamlit as st
import gsheets_service
import pandas as pd
import uuid

def show():
    st.header("Μητρώο")
    st.caption("Διαχείριση και επισκόπηση του χαρτοφυλακίου ακινήτων και του πελατολογίου.")

    try:
        properties_df = gsheets_service.fetch_all_properties()
        tenants_df = gsheets_service.fetch_all_tenants()
        leases_df = gsheets_service.fetch_all_leases()
    except Exception as e:
        st.error(f"Σφάλμα κατά τη φόρτωση δεδομένων: {e}")
        return

    tab_prop_list, tab_tenant_list, tab_prop_new, tab_tenant_new = st.tabs([
        "🏢 Ακίνητα", "👥 Ενοικιαστές", "➕ Νέο Ακίνητο", "➕ Νέος Ενοικ."
    ])

    # --- ΚΑΡΤΕΛΑ 1: ΛΙΣΤΑ ΑΚΙΝΗΤΩΝ ---
    with tab_prop_list:
        st.subheader("Καταχωρημένα Ακίνητα")
        if properties_df.empty:
            st.info("Δεν υπάρχουν καταχωρημένα ακίνητα.")
        else:
            prop_data = []
            for _, prop in properties_df.iterrows():
                owners_list = []
                for i in range(1, 4):
                    n = str(prop.get(f'Name_{i}', '')).strip()
                    s = str(prop.get(f'Surname_{i}', '')).strip()
                    r = str(prop.get(f'Right_{i}', '')).strip()
                    
                    # ΑΣΦΑΛΗΣ ΜΕΤΑΤΡΟΠΗ ΠΟΣΟΣΤΟΥ: Αν είναι κενό, γίνεται 0.0
                    p_val = prop.get(f'Perc_{i}')
                    p = pd.to_numeric(p_val, errors='coerce')
                    if pd.isna(p): p = 0.0
                    
                    # Ελέγχουμε αν υπάρχει όνομα και αν το ποσοστό δεν είναι "NaN" και είναι > 0
                    if n and n != 'nan' and p > 0:
                        owners_list.append(f"{n} {s} ({r} {p}%)")
                
                owners_info = " | ".join(owners_list) if owners_list else "Δεν έχουν οριστεί ιδιοκτήτες"

                prop_data.append({
                    "Χαρακτηριστικό": prop.get("Χαρακτηριστικό", "-"),
                    "Διεύθυνση": f"{prop.get('Διεύθυνση', '')} {prop.get('Αριθμός', '')}",
                    "Περιοχή": prop.get("Περιοχή/Δήμος", ""),
                    "Ιδιοκτησιακό Καθεστώς": owners_info
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
                t_id = str(tenant.get("Tenant_ID", ""))
                if t_id and t_id != 'nan':
                    linked_prop_charact = "-"
                    
                    if not leases_df.empty and not properties_df.empty:
                        # Ασφαλής αναζήτηση
                        leases_df['Tenant_ID'] = leases_df['Tenant_ID'].astype(str)
                        t_leases = leases_df[leases_df["Tenant_ID"].str.contains(t_id, na=False, regex=False)]
                        if not t_leases.empty:
                            p_id = t_leases.iloc[-1]["Property_ID"]
                            p_match = properties_df[properties_df["Property_ID"] == p_id]
                            if not p_match.empty:
                                linked_prop_charact = p_match.iloc[0].get("Χαρακτηριστικό", "-")

                    tenant_data.append({
                        "Επώνυμο": str(tenant.get("Επώνυμο", "")).replace('nan', ''),
                        "Όνομα": str(tenant.get("Όνομα", "")).replace('nan', ''),
                        "ΑΦΜ": str(tenant.get("ΑΦΜ", "")).replace('nan', ''),
                        "Κινητό": str(tenant.get("Κινητό", "-")).replace('nan', '-'),
                        "Email": str(tenant.get("Email", "-")).replace('nan', '-'),
                        "Συνδεδεμένο Ακίνητο": linked_prop_charact
                    })
            if tenant_data:
                st.dataframe(pd.DataFrame(tenant_data), use_container_width=True, hide_index=True)
            else:
                st.info("Δεν βρέθηκαν έγκυρα δεδομένα ενοικιαστών.")

    # --- ΚΑΡΤΕΛΑ 3: ΦΟΡΜΑ ΝΕΟΥ ΑΚΙΝΗΤΟΥ ---
    with tab_prop_new:
        with st.form("new_property_form", clear_on_submit=True):
            charact = st.text_input("Χαρακτηριστικό Ακινήτου *")
            atak = st.text_input("ΑΤΑΚ *")
            nomos = st.text_input("Νομός", value="Αττικής") 
            dimos = st.text_input("Περιοχή / Δήμος *")
            
            col1, col2 = st.columns(2)
            with col1: address = st.text_input("Οδός *")
            with col2: number = st.text_input("Αριθμός")
            
            col3, col4 = st.columns(2)
            with col3: floor = st.text_input("Όροφος")
            with col4: sqm = st.number_input("Επιφάνεια (m2) *", min_value=0.0, step=1.0)
            
            st.subheader("Ιδιοκτήτες & Δικαιώματα")
            owner_data = []
            for i in range(1, 4):
                with st.expander(f"Εγγραφή Δικαιώματος {i}", expanded=(i==1)):
                    c1, c2 = st.columns(2)
                    n = c1.text_input(f"Όνομα", key=f"n{i}", value="Γιώργος" if i==1 else "")
                    s = c2.text_input(f"Επώνυμο", key=f"s{i}", value="Μπαλτάσης" if i==1 else "")
                    c3, c4, c5 = st.columns(3)
                    afm = c3.text_input(f"ΑΦΜ", key=f"afm{i}")
                    right = c4.selectbox(f"Είδος", ["Πλήρης Κυριότητα", "Επικαρπία", "Ψιλή Κυριότητα"], key=f"r{i}")
                    perc = c5.number_input(f"Ποσοστό %", min_value=0.0, max_value=100.0, value=100.0 if i==1 else 0.0, step=1.0, key=f"p{i}")
                    owner_data.extend([n, s, afm, right, perc])
                
            submit_prop = st.form_submit_button("Αποθήκευση Ακινήτου", use_container_width=True)
            
            if submit_prop:
                if charact and atak and address and sqm > 0 and owner_data[0]:
                    prop_id = f"PR-{uuid.uuid4().hex[:6].upper()}"
                    row_data = [prop_id, atak, nomos, dimos, address, number, floor, sqm, charact] + owner_data
                    try:
                        gsheets_service.add_property(row_data)
                        st.success("Το ακίνητο αποθηκεύτηκε επιτυχώς!")
                    except Exception as e:
                        st.error(f"Σφάλμα: {e}")
                else:
                    st.warning("Συμπληρώστε τα υποχρεωτικά πεδία και τον 1ο Ιδιοκτήτη.")

    # --- ΚΑΡΤΕΛΑ 4: ΦΟΡΜΑ ΝΕΟΥ ΕΝΟΙΚΙΑΣΤΗ ---
    with tab_tenant_new:
        with st.form("new_tenant_form", clear_on_submit=True):
            fname = st.text_input("Όνομα *")
            lname = st.text_input("Επώνυμο *")
            afm = st.text_input("ΑΦΜ *")
            phone = st.text_input("Κινητό Τηλέφωνο")
            email = st.text_input("Email")
            
            submit_tenant = st.form_submit_button("Αποθήκευση Ενοικιαστή", use_container_width=True)
            
            if submit_tenant:
                if fname and lname and afm:
                    tenant_id = f"TN-{uuid.uuid4().hex[:6].upper()}"
                    row_data = [tenant_id, fname, lname, afm, phone, email]
                    try:
                        gsheets_service.add_tenant(row_data)
                        st.success("Ο ενοικιαστής αποθηκεύτηκε επιτυχώς!")
                    except Exception as e:
                        st.error(f"Σφάλμα: {e}")
                else:
                    st.warning("Παρακαλώ συμπληρώστε Όνομα, Επώνυμο, ΑΦΜ.")
