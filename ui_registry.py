import streamlit as st
import gsheets_service
import pandas as pd
import uuid

MONTHS_DICT = {1:"Ιανουάριος", 2:"Φεβρουάριος", 3:"Μάρτιος", 4:"Απρίλιος", 5:"Μάιος", 6:"Ιούνιος", 
               7:"Ιούλιος", 8:"Αύγουστος", 9:"Σεπτέμβριος", 10:"Οκτώβριος", 11:"Νοέμβριος", 12:"Δεκέμβριος"}

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

    tab_prop_list, tab_tenant_list, tab_prop_new, tab_tenant_new, tab_prop_edit, tab_tenant_edit = st.tabs([
        "🏢 Ακίνητα", "👥 Ενοικιαστές", "➕ Νέο Ακίνητο", "➕ Νέος Ενοικ.", "✏️ Επεξ. Ακιν.", "✏️ Επεξ. Ενοικ."
    ])

    with tab_prop_list:
        if properties_df.empty: st.info("Δεν υπάρχουν καταχωρημένα ακίνητα.")
        else:
            prop_data = []
            for _, prop in properties_df.iterrows():
                owners_list = []
                for i in range(1, 4):
                    n, s, r = str(prop.get(f'Name_{i}', '')).strip(), str(prop.get(f'Surname_{i}', '')).strip(), str(prop.get(f'Right_{i}', '')).strip()
                    p = pd.to_numeric(str(prop.get(f'Perc_{i}', '')).replace(',', '.'), errors='coerce')
                    if pd.isna(p): p = 0.0
                    if n and p > 0:
                        p_display = str(p).replace('.', ',')
                        if p_display.endswith(',0'): p_display = p_display[:-2]
                        owners_list.append(f"{n} {s} ({r} {p_display}%)")
                
                e_months_raw = str(prop.get("Extra_Bills_Months", ""))
                e_months_text = ", ".join([MONTHS_DICT[int(m)] for m in e_months_raw.split(',') if m.strip().isdigit()])
                
                prop_data.append({
                    "Χαρακτηριστικό": prop.get("Χαρακτηριστικό", "-"),
                    "Διεύθυνση": f"{prop.get('Διεύθυνση', '')} {prop.get('Αριθμός', '')}",
                    "Μήνες Λογαριασμών": e_months_text if e_months_text else "-",
                    "Ιδιοκτησιακό Καθεστώς": " | ".join(owners_list) if owners_list else "Μη ορισμένο"
                })
            st.dataframe(pd.DataFrame(prop_data), use_container_width=True, hide_index=True)

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
                            p_match = properties_df[properties_df["Property_ID"] == t_leases.iloc[-1]["Property_ID"]]
                            if not p_match.empty: linked_prop_charact = p_match.iloc[0].get("Χαρακτηριστικό", "-")
                    tenant_data.append({
                        "Ονοματεπώνυμο": f"{str(tenant.get('Επώνυμο', ''))} {str(tenant.get('Όνομα', ''))}",
                        "ΑΦΜ": str(tenant.get("ΑΦΜ", "")),
                        "Επικοινωνία": f"{str(tenant.get('Κινητό', ''))} | {str(tenant.get('Email', ''))}",
                        "Ακίνητο": linked_prop_charact
                    })
            if tenant_data: st.dataframe(pd.DataFrame(tenant_data), use_container_width=True, hide_index=True)

    with tab_prop_new:
        with st.form("new_property_form", clear_on_submit=True):
            charact, atak, dimos = st.text_input("Χαρακτηριστικό Ακινήτου *"), st.text_input("ΑΤΑΚ *"), st.text_input("Περιοχή / Δήμος *")
            nomos = st.text_input("Νομός", value="ΑΤΤΙΚΗΣ") 
            col1, col2 = st.columns(2)
            with col1: address = st.text_input("Οδός *")
            with col2: number = st.text_input("Αριθμός")
            col3, col4 = st.columns(2)
            with col3: floor = st.text_input("Όροφος")
            with col4: sqm_input = st.text_input("Επιφάνεια (m2) *", value="0")
            
            st.subheader("Ημερολόγιο Εξόδων (Προαιρετικό)")
            extra_months = st.multiselect("Επιλέξτε Μήνες που εκδίδονται Λογαριασμοί (π.χ. Νερό, Κοινόχρηστα)", options=list(MONTHS_DICT.keys()), format_func=lambda x: MONTHS_DICT[x])
            
            st.subheader("Ιδιοκτήτες")
            owner_data = []
            for i in range(1, 4):
                with st.expander(f"Ιδιοκτήτης {i}", expanded=(i==1)):
                    c1, c2 = st.columns(2)
                    n = c1.text_input(f"Όνομα", key=f"n{i}")
                    s = c2.text_input(f"Επώνυμο", key=f"s{i}")
                    c3, c4, c5 = st.columns(3)
                    afm = c3.text_input(f"ΑΦΜ", key=f"afm{i}")
                    right = c4.selectbox(f"Είδος", ["Πλήρης Κυριότητα", "Επικαρπία", "Ψιλή Κυριότητα"], key=f"r{i}")
                    perc_input = c5.text_input(f"Ποσοστό %", value="100" if i==1 else "0", key=f"p{i}")
                    owner_data.extend([n, s, afm, right, perc_input])
                
            if st.form_submit_button("Αποθήκευση Ακινήτου", use_container_width=True):
                sqm_val = pd.to_numeric(sqm_input.replace(',', '.'), errors='coerce')
                if pd.isna(sqm_val): sqm_val = 0.0
                if charact and atak and address and sqm_val > 0 and owner_data[0]:
                    try:
                        extra_str = ",".join(map(str, extra_months))
                        gsheets_service.add_property([f"PR-{uuid.uuid4().hex[:6].upper()}", atak, nomos, dimos, address, number, floor, sqm_input, charact] + owner_data + [extra_str])
                        st.success("Το ακίνητο αποθηκεύτηκε επιτυχώς!")
                    except Exception as e: st.error(f"Σφάλμα: {e}")
                else: st.warning("Συμπληρώστε τα υποχρεωτικά πεδία και τον 1ο Ιδιοκτήτη.")

    with tab_prop_edit:
        if properties_df.empty: st.warning("Δεν υπάρχουν ακίνητα.")
        else:
            edit_options = {row["Property_ID"]: f"{row.get('Χαρακτηριστικό', '')} ({row.get('Διεύθυνση', '')})" for _, row in properties_df.iterrows()}
            selected_edit_id = st.selectbox("Επιλέξτε Ακίνητο", options=list(edit_options.keys()), format_func=lambda x: edit_options[x])
            
            if selected_edit_id:
                sel_prop = properties_df[properties_df["Property_ID"] == selected_edit_id].iloc[0]
                with st.form("edit_property_form"):
                    e_charact, e_atak = st.text_input("Χαρακτηριστικό", value=str(sel_prop.get("Χαρακτηριστικό", ""))), st.text_input("ΑΤΑΚ", value=str(sel_prop.get("ΑΤΑΚ", "")))
                    e_nomos, e_dimos = st.text_input("Νομός", value=str(sel_prop.get("Νομός", ""))), st.text_input("Περιοχή / Δήμος", value=str(sel_prop.get("Περιοχή/Δήμος", "")))
                    ec1, ec2 = st.columns(2)
                    with ec1: e_address = st.text_input("Οδός", value=str(sel_prop.get("Διεύθυνση", "")))
                    with ec2: e_number = st.text_input("Αριθμός", value=str(sel_prop.get("Αριθμός", "")))
                    ec3, ec4 = st.columns(2)
                    with ec3: e_floor = st.text_input("Όροφος", value=str(sel_prop.get("Όροφος", "")))
                    with ec4: e_sqm = st.text_input("Επιφάνεια (m2)", value=str(sel_prop.get("Επιφάνεια m2", "")))
                    
                    st.subheader("Ημερολόγιο Εξόδων (Προαιρετικό)")
                    sel_extra_raw = str(sel_prop.get("Extra_Bills_Months", ""))
                    sel_extra_defs = [int(x.strip()) for x in sel_extra_raw.split(',') if x.strip().isdigit()]
                    e_extra_months = st.multiselect("Επιλέξτε Μήνες που εκδίδονται Λογαριασμοί", options=list(MONTHS_DICT.keys()), default=sel_extra_defs, format_func=lambda x: MONTHS_DICT[x])

                    st.subheader("Ιδιοκτήτες")
                    e_owner_data = []
                    for i in range(1, 4):
                        with st.expander(f"Ιδιοκτήτης {i}", expanded=(i==1)):
                            rc1, rc2 = st.columns(2)
                            n, s = rc1.text_input(f"Όνομα", key=f"en{i}", value=str(sel_prop.get(f"Name_{i}", ""))), rc2.text_input(f"Επώνυμο", key=f"es{i}", value=str(sel_prop.get(f"Surname_{i}", "")))
                            rc3, rc4, rc5 = st.columns(3)
                            afm_val = str(sel_prop.get(f"AFM_{i}", ""))
                            if len(afm_val) == 8: afm_val = "0" + afm_val
                            afm = rc3.text_input(f"ΑΦΜ", key=f"eafm{i}", value=afm_val)
                            r_opts, curr_r = ["Πλήρης Κυριότητα", "Επικαρπία", "Ψιλή Κυριότητα"], str(sel_prop.get(f"Right_{i}", ""))
                            right = rc4.selectbox(f"Είδος", r_opts, index=r_opts.index(curr_r) if curr_r in r_opts else 0, key=f"er{i}")
                            p_val = str(sel_prop.get(f"Perc_{i}", "")).replace('.', ',')
                            perc = rc5.text_input(f"Ποσοστό %", value="0" if p_val == "" else p_val, key=f"ep{i}")
                            e_owner_data.extend([n, s, afm, right, perc])
                            
                    update_btn = st.form_submit_button("Αποθήκευση Αλλαγών", type="primary")
                    
                if st.button("🗑️ Οριστική Διαγραφή Ακινήτου"):
                    try:
                        gsheets_service.delete_property(selected_edit_id)
                        st.success("Το ακίνητο διαγράφηκε! Ανανεώστε τη σελίδα.")
                    except Exception as e: st.error(f"Σφάλμα: {e}")

                if update_btn:
                    try:
                        e_extra_str = ",".join(map(str, e_extra_months))
                        gsheets_service.update_property(selected_edit_id, [selected_edit_id, e_atak, e_nomos, e_dimos, e_address, e_number, e_floor, e_sqm, e_charact] + e_owner_data + [e_extra_str])
                        st.success("Αποθηκεύτηκαν! Ανανεώστε (Refresh) τη σελίδα.")
                    except Exception as e: st.error(f"Σφάλμα: {e}")

    with tab_tenant_new:
        with st.form("new_tenant_form", clear_on_submit=True):
            fname, lname, afm = st.text_input("Όνομα *"), st.text_input("Επώνυμο *"), st.text_input("ΑΦΜ *")
            phone, email = st.text_input("Κινητό Τηλέφωνο"), st.text_input("Email")
            if st.form_submit_button("Αποθήκευση Ενοικιαστή", use_container_width=True):
                if fname and lname and afm:
                    try:
                        gsheets_service.add_tenant([f"TN-{uuid.uuid4().hex[:6].upper()}", fname, lname, afm, phone, email])
                        st.success("Ο ενοικιαστής αποθηκεύτηκε!")
                    except Exception as e: st.error(f"Σφάλμα: {e}")
                else: st.warning("Παρακαλώ συμπληρώστε Όνομα, Επώνυμο, ΑΦΜ.")

    with tab_tenant_edit:
        if tenants_df.empty: st.warning("Δεν υπάρχουν ενοικιαστές.")
        else:
            t_edit_opts = {row["Tenant_ID"]: f"{row.get('Όνομα', '')} {row.get('Επώνυμο', '')} (ΑΦΜ: {row.get('ΑΦΜ', '')})" for _, row in tenants_df.iterrows()}
            selected_t_edit = st.selectbox("Επιλέξτε Ενοικιαστή", options=list(t_edit_opts.keys()), format_func=lambda x: t_edit_opts[x])
            
            if selected_t_edit:
                sel_ten = tenants_df[tenants_df["Tenant_ID"] == selected_t_edit].iloc[0]
                with st.form("edit_tenant_form"):
                    e_t_fname, e_t_lname = st.text_input("Όνομα *", value=str(sel_ten.get("Όνομα", ""))), st.text_input("Επώνυμο *", value=str(sel_ten.get("Επώνυμο", "")))
                    afm_v = str(sel_ten.get("ΑΦΜ", ""))
                    if len(afm_v) == 8: afm_v = "0" + afm_v
                    e_t_afm = st.text_input("ΑΦΜ *", value=afm_v)
                    e_t_phone, e_t_email = st.text_input("Κινητό Τηλέφωνο", value=str(sel_ten.get("Κινητό", ""))), st.text_input("Email", value=str(sel_ten.get("Email", "")))
                    upd_t_btn = st.form_submit_button("Αποθήκευση Αλλαγών", type="primary")
                    
                if st.button("🗑️ Οριστική Διαγραφή Ενοικιαστή"):
                    try:
                        gsheets_service.delete_tenant(selected_t_edit)
                        st.success("Ο ενοικιαστής διαγράφηκε! Ανανεώστε τη σελίδα.")
                    except Exception as e: st.error(f"Σφάλμα: {e}")

                if upd_t_btn:
                    if e_t_fname and e_t_lname and e_t_afm:
                        try:
                            gsheets_service.update_tenant(selected_t_edit, [selected_t_edit, e_t_fname, e_t_lname, e_t_afm, e_t_phone, e_t_email])
                            st.success("Αποθηκεύτηκαν! Ανανεώστε τη σελίδα.")
                        except Exception as e: st.error(f"Σφάλμα: {e}")
                    else: st.warning("Παρακαλώ συμπληρώστε Όνομα, Επώνυμο, ΑΦΜ.")
