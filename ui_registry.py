import streamlit as st
import gsheets_service
import pandas as pd
import uuid

COMMON_CSS = """
<style>
    .custom-table { width: 100% !important; border-collapse: collapse; font-family: sans-serif; font-size: 14px; margin-bottom: 2rem; }
    .custom-table th { text-align: left !important; background-color: #f0f2f6; padding: 12px; border-bottom: 1px solid #e6e9ef; color: #31333F; }
    .custom-table td { text-align: left !important; word-wrap: break-word !important; white-space: normal !important; padding: 12px; border-bottom: 1px solid #e6e9ef; color: #31333F; vertical-align: top; }
</style>
"""

def show():
    st.markdown(COMMON_CSS, unsafe_allow_html=True)
    st.header("Μητρώο")
    st.caption("Διαχείριση και επισκόπηση του χαρτοφυλακίου ακινήτων και του πελατολογίου.")

    try:
        properties_df = gsheets_service.fetch_all_properties()
        tenants_df = gsheets_service.fetch_all_tenants()
        leases_df = gsheets_service.fetch_all_leases()
    except Exception as e:
        st.error(f"Σφάλμα κατά τη φόρτωση δεδομένων: {e}")
        return

    tab_prop_list, tab_tenant_list, tab_prop_new, tab_prop_edit, tab_tenant_new, tab_tenant_edit = st.tabs([
        "🏢 Ακίνητα", "👥 Ενοικιαστές", "➕ Νέο Ακίνητο", "✏️ Επεξ. Ακιν.", "➕ Νέος Ενοικ.", "✏️ Επεξ. Ενοικ."
    ])

    # --- 1. ΛΙΣΤΑ ΑΚΙΝΗΤΩΝ ---
    with tab_prop_list:
        if properties_df.empty: st.info("Δεν υπάρχουν καταχωρημένα ακίνητα.")
        else:
            prop_data = []
            for _, prop in properties_df.iterrows():
                owners_list = []
                for i in range(1, 4):
                    n = str(prop.get(f'Name_{i}', '')).strip()
                    s = str(prop.get(f'Surname_{i}', '')).strip()
                    r = str(prop.get(f'Right_{i}', '')).strip()
                    p_val = str(prop.get(f'Perc_{i}', '')).replace(',', '.')
                    p = pd.to_numeric(p_val, errors='coerce')
                    if pd.isna(p): p = 0.0
                    if n and p > 0:
                        p_display = str(p).replace('.', ',')
                        if p_display.endswith(',0'): p_display = p_display[:-2]
                        owners_list.append(f"{n} {s} ({r} {p_display}%)")
                owners_info = "<br>".join(owners_list) if owners_list else "Μη ορισμένο"
                prop_data.append({
                    "Χαρακτηριστικό": prop.get("Χαρακτηριστικό", "-"),
                    "Διεύθυνση": f"{prop.get('Διεύθυνση', '')} {prop.get('Αριθμός', '')}",
                    "Περιοχή": prop.get("Περιοχή/Δήμος", ""),
                    "Ιδιοκτησιακό Καθεστώς": owners_info
                })
            st.write(pd.DataFrame(prop_data).to_html(classes='custom-table', escape=False, index=False, justify='left'), unsafe_allow_html=True)

    # --- 2. ΛΙΣΤΑ ΕΝΟΙΚΙΑΣΤΩΝ ---
    with tab_tenant_list:
        if tenants_df.empty: st.info("Δεν υπάρχουν καταχωρημένοι ενοικιαστές.")
        else:
            tenant_data = []
            for _, tenant in tenants_df.iterrows():
                t_id = str(tenant.get("Tenant_ID", ""))
                if t_id:
                    linked_prop_charact = "-"
                    if not leases_df.empty and not properties_df.empty:
                        leases_df['Tenant_ID'] = leases_df['Tenant_ID'].astype(str)
                        t_leases = leases_df[leases_df["Tenant_ID"].str.contains(t_id, na=False, regex=False)]
                        if not t_leases.empty:
                            p_id = t_leases.iloc[-1]["Property_ID"]
                            p_match = properties_df[properties_df["Property_ID"] == p_id]
                            if not p_match.empty:
                                linked_prop_charact = p_match.iloc[0].get("Χαρακτηριστικό", "-")
                    tenant_data.append({
                        "Ονοματεπώνυμο": f"{str(tenant.get('Επώνυμο', ''))} {str(tenant.get('Όνομα', ''))}",
                        "ΑΦΜ": str(tenant.get("ΑΦΜ", "")),
                        "Επικοινωνία": f"{str(tenant.get('Κινητό', ''))}<br>{str(tenant.get('Email', ''))}",
                        "Ακίνητο": linked_prop_charact
                    })
            if tenant_data: st.write(pd.DataFrame(tenant_data).to_html(classes='custom-table', escape=False, index=False, justify='left'), unsafe_allow_html=True)

    # --- 3. ΝΕΟ ΑΚΙΝΗΤΟ ---
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
            with col4: sqm_input = st.text_input("Επιφάνεια (m2) *", value="0")
            
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
                    perc_input = c5.text_input(f"Ποσοστό %", value="100" if i==1 else "0", key=f"p{i}")
                    owner_data.extend([n, s, afm, right, perc_input])
                
            if st.form_submit_button("Αποθήκευση Ακινήτου", use_container_width=True):
                sqm_val = pd.to_numeric(sqm_input.replace(',', '.'), errors='coerce')
                if pd.isna(sqm_val): sqm_val = 0.0
                if charact and atak and address and sqm_val > 0 and owner_data[0]:
                    prop_id = f"PR-{uuid.uuid4().hex[:6].upper()}"
                    row_data = [prop_id, atak, nomos, dimos, address, number, floor, sqm_input, charact] + owner_data
                    try:
                        gsheets_service.add_property(row_data)
                        st.success("Το ακίνητο αποθηκεύτηκε επιτυχώς!")
                    except Exception as e: st.error(f"Σφάλμα: {e}")
                else: st.warning("Συμπληρώστε τα υποχρεωτικά πεδία και τον 1ο Ιδιοκτήτη.")

    # --- 4. ΕΠΕΞΕΡΓΑΣΙΑ ΑΚΙΝΗΤΟΥ ---
    with tab_prop_edit:
        if properties_df.empty: st.warning("Δεν υπάρχουν ακίνητα.")
        else:
            edit_options = {row["Property_ID"]: f"{row.get('Χαρακτηριστικό', '')} ({row.get('Διεύθυνση', '')})" for _, row in properties_df.iterrows()}
            selected_edit_id = st.selectbox("Επιλέξτε Ακίνητο", options=list(edit_options.keys()), format_func=lambda x: edit_options[x])
            
            if selected_edit_id:
                sel_prop = properties_df[properties_df["Property_ID"] == selected_edit_id].iloc[0]
                with st.form("edit_property_form"):
                    e_charact = st.text_input("Χαρακτηριστικό Ακινήτου", value=str(sel_prop.get("Χαρακτηριστικό", "")))
                    e_atak = st.text_input("ΑΤΑΚ", value=str(sel_prop.get("ΑΤΑΚ", "")))
                    e_nomos = st.text_input("Νομός", value=str(sel_prop.get("Νομός", "")))
                    e_dimos = st.text_input("Περιοχή / Δήμος", value=str(sel_prop.get("Περιοχή/Δήμος", "")))
                    ec1, ec2 = st.columns(2)
                    with ec1: e_address = st.text_input("Οδός", value=str(sel_prop.get("Διεύθυνση", "")))
                    with ec2: e_number = st.text_input("Αριθμός", value=str(sel_prop.get("Αριθμός", "")))
                    ec3, ec4 = st.columns(2)
                    with ec3: e_floor = st.text_input("Όροφος", value=str(sel_prop.get("Όροφος", "")))
                    with ec4: e_sqm = st.text_input("Επιφάνεια (m2)", value=str(sel_prop.get("Επιφάνεια m2", "")))
                    
                    st.subheader("Ιδιοκτήτες")
                    e_owner_data = []
                    for i in range(1, 4):
                        with st.expander(f"Ιδιοκτήτης {i}", expanded=(i==1)):
                            rc1, rc2 = st.columns(2)
                            n = rc1.text_input(f"Όνομα", key=f"en{i}", value=str(sel_prop.get(f"Name_{i}", "")))
                            s = rc2.text_input(f"Επώνυμο", key=f"es{i}", value=str(sel_prop.get(f"Surname_{i}", "")))
                            rc3, rc4, rc5 = st.columns(3)
                            
                            afm_val = str(sel_prop.get(f"AFM_{i}", ""))
                            if len(afm_val) == 8: afm_val = "0" + afm_val
                            afm = rc3.text_input(f"ΑΦΜ", key=f"eafm{i}", value=afm_val)
                            
                            right_options = ["Πλήρης Κυριότητα", "Επικαρπία", "Ψιλή Κυριότητα"]
                            curr_right = str(sel_prop.get(f"Right_{i}", ""))
                            r_idx = right_options.index(curr_right) if curr_right in right_options else 0
                            right = rc4.selectbox(f"Είδος", right_options, index=r_idx, key=f"er{i}")
                            
                            p_val = str(sel_prop.get(f"Perc_{i}", "")).replace('.', ',')
                            if p_val == "": p_val = "0"
                            perc = rc5.text_input(f"Ποσοστό %", value=p_val, key=f"ep{i}")
                            e_owner_data.extend([n, s, afm, right, perc])
                            
                    update_btn = st.form_submit_button("Αποθήκευση Αλλαγών", type="primary")
                    
                if st.button("🗑️ Οριστική Διαγραφή Ακινήτου"):
                    try:
                        gsheets_service.delete_property(selected_edit_id)
                        st.success("Το ακίνητο διαγράφηκε! Ανανεώστε τη σελίδα.")
                    except Exception as e: st.error(f"Σφάλμα διαγραφής: {e}")

                if update_btn:
                    new_row = [selected_edit_id, e_atak, e_nomos, e_dimos, e_address, e_number, e_floor, e_sqm, e_charact] + e_owner_data
                    try:
                        gsheets_service.update_property(selected_edit_id, new_row)
                        st.success("Οι αλλαγές αποθηκεύτηκαν! Ανανεώστε (Refresh) τη σελίδα.")
                    except Exception as e: st.error(f"Σφάλμα επεξεργασίας: {e}")

    # --- 5. ΝΕΟΣ ΕΝΟΙΚΙΑΣΤΗΣ ---
    with tab_tenant_new:
        with st.form("new_tenant_form", clear_on_submit=True):
            fname = st.text_input("Όνομα *")
            lname = st.text_input("Επώνυμο *")
            afm = st.text_input("ΑΦΜ *")
            phone = st.text_input("Κινητό Τηλέφωνο")
            email = st.text_input("Email")
            if st.form_submit_button("Αποθήκευση Ενοικιαστή", use_container_width=True):
                if fname and lname and afm:
                    tenant_id = f"TN-{uuid.uuid4().hex[:6].upper()}"
                    row_data = [tenant_id, fname, lname, afm, phone, email]
                    try:
                        gsheets_service.add_tenant(row_data)
                        st.success("Ο ενοικιαστής αποθηκεύτηκε επιτυχώς!")
                    except Exception as e: st.error(f"Σφάλμα: {e}")
                else: st.warning("Παρακαλώ συμπληρώστε Όνομα, Επώνυμο, ΑΦΜ.")

    # --- 6. ΕΠΕΞΕΡΓΑΣΙΑ ΕΝΟΙΚΙΑΣΤΗ (ΝΕΑ) ---
    with tab_tenant_edit:
        if tenants_df.empty: st.warning("Δεν υπάρχουν ενοικιαστές.")
        else:
            t_edit_opts = {row["Tenant_ID"]: f"{row.get('Όνομα', '')} {row.get('Επώνυμο', '')} (ΑΦΜ: {row.get('ΑΦΜ', '')})" for _, row in tenants_df.iterrows()}
            selected_t_edit = st.selectbox("Επιλέξτε Ενοικιαστή", options=list(t_edit_opts.keys()), format_func=lambda x: t_edit_opts[x])
            
            if selected_t_edit:
                sel_ten = tenants_df[tenants_df["Tenant_ID"] == selected_t_edit].iloc[0]
                with st.form("edit_tenant_form"):
                    e_t_fname = st.text_input("Όνομα *", value=str(sel_ten.get("Όνομα", "")))
                    e_t_lname = st.text_input("Επώνυμο *", value=str(sel_ten.get("Επώνυμο", "")))
                    
                    afm_v = str(sel_ten.get("ΑΦΜ", ""))
                    if len(afm_v) == 8: afm_v = "0" + afm_v
                    e_t_afm = st.text_input("ΑΦΜ *", value=afm_v)
                    
                    e_t_phone = st.text_input("Κινητό Τηλέφωνο", value=str(sel_ten.get("Κινητό", "")))
                    e_t_email = st.text_input("Email", value=str(sel_ten.get("Email", "")))
                    
                    upd_t_btn = st.form_submit_button("Αποθήκευση Αλλαγών", type="primary")
                    
                if st.button("🗑️ Οριστική Διαγραφή Ενοικιαστή"):
                    try:
                        gsheets_service.delete_tenant(selected_t_edit)
                        st.success("Ο ενοικιαστής διαγράφηκε! Ανανεώστε τη σελίδα.")
                    except Exception as e: st.error(f"Σφάλμα διαγραφής: {e}")

                if upd_t_btn:
                    if e_t_fname and e_t_lname and e_t_afm:
                        new_t_row = [selected_t_edit, e_t_fname, e_t_lname, e_t_afm, e_t_phone, e_t_email]
                        try:
                            gsheets_service.update_tenant(selected_t_edit, new_t_row)
                            st.success("Οι αλλαγές αποθηκεύτηκαν! Ανανεώστε τη σελίδα.")
                        except Exception as e: st.error(f"Σφάλμα επεξεργασίας: {e}")
                    else: st.warning("Παρακαλώ συμπληρώστε Όνομα, Επώνυμο, ΑΦΜ.")
