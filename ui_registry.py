import streamlit as st
import gsheets_service
import pandas as pd
import uuid
from datetime import date, datetime

MONTHS_DICT = {1:"Ιανουάριος", 2:"Φεβρουάριος", 3:"Μάρτιος", 4:"Απρίλιος", 5:"Μάιος", 6:"Ιούνιος", 
               7:"Ιούλιος", 8:"Αύγουστος", 9:"Σεπτέμβριος", 10:"Οκτώβριος", 11:"Νοέμβριος", 12:"Δεκέμβριος"}

def show():
    st.header("Μητρώο")
    st.caption("Διαχείριση και επισκόπηση του χαρτοφυλακίου ακινήτων, του πελατολογίου και των συμβολαίων.")

    try:
        properties_df = gsheets_service.fetch_all_properties()
        tenants_df = gsheets_service.fetch_all_tenants()
        leases_df = gsheets_service.fetch_all_leases()
        insurances_df = gsheets_service.fetch_all_insurances()
    except Exception as e:
        st.error(f"Σφάλμα κατά τη φόρτωση δεδομένων: {e}")
        return

    # Προσθήκη των 3 νέων καρτελών
    tab_prop_list, tab_tenant_list, tab_ins_list, tab_prop_new, tab_tenant_new, tab_ins_new, tab_prop_edit, tab_tenant_edit, tab_ins_edit = st.tabs([
        "🏢 Ακίνητα", "👥 Ενοικιαστές", "🛡️ Ασφαλιστήρια", 
        "➕ Νέο Ακίνητο", "➕ Νέος Ενοικ.", "➕ Νέο Ασφαλ.", 
        "✏️ Επεξ. Ακιν.", "✏️ Επεξ. Ενοικ.", "✏️ Επεξ. Ασφαλ."
    ])

    # ==========================================
    # 1. ΛΙΣΤΕΣ (ΙΣΤΟΡΙΚΟ)
    # ==========================================
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

    with tab_ins_list:
        if insurances_df.empty: st.info("Δεν υπάρχουν καταχωρημένα ασφαλιστήρια συμβόλαια.")
        else:
            ins_data = []
            for _, ins in insurances_df.iterrows():
                p_id = str(ins.get("Property_ID", ""))
                p_charact = "-"
                if not properties_df.empty:
                    p_match = properties_df[properties_df["Property_ID"] == p_id]
                    if not p_match.empty: p_charact = str(p_match.iloc[0].get("Χαρακτηριστικό", "-"))
                
                prem = pd.to_numeric(str(ins.get('Premium', '0')).replace(',', '.'), errors='coerce')
                
                ins_data.append({
                    "Ακίνητο": p_charact,
                    "Κατηγορία": str(ins.get("Category", "")),
                    "Εταιρεία (Αρ. Συμβολαίου)": f"{ins.get('Company', '')} ({ins.get('Contract_Number', '')})",
                    "Λήξη / Ανανέωση": str(ins.get("Renewal_Date", "")),
                    "Ασφάλιστρο": f"{prem:.2f} €".replace('.', ',') if pd.notna(prem) and prem > 0 else "-"
                })
            st.dataframe(pd.DataFrame(ins_data), use_container_width=True, hide_index=True)

    # ==========================================
    # 2. ΝΕΕΣ ΕΓΓΡΑΦΕΣ
    # ==========================================
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

    with tab_ins_new:
        if properties_df.empty: st.warning("Πρέπει να καταχωρήσετε πρώτα ένα Ακίνητο.")
        else:
            prop_options = {row["Property_ID"]: f"{row.get('Χαρακτηριστικό', '')} ({row.get('Διεύθυνση', '')})" for _, row in properties_df.iterrows()}
            
            with st.form("new_insurance_form", clear_on_submit=True):
                i_prop = st.selectbox("Ακίνητο *", options=list(prop_options.keys()), format_func=lambda x: prop_options[x])
                
                ic1, ic2 = st.columns(2)
                with ic1: i_cat = st.selectbox("Κατηγορία Κινδύνου *", ["Ασφάλιση Πυρός / Σεισμού", "Αστική Ευθύνη", "Νομική Προστασία", "Άλλο"])
                with ic2: i_comp = st.text_input("Ασφαλιστική Εταιρεία *")
                
                ic3, ic4, ic5 = st.columns(3)
                with ic3: i_num = st.text_input("Αριθμός Συμβολαίου *")
                with ic4: i_date = st.date_input("Ημ/νία Ανανέωσης (Επόμενη) *", value=date.today())
                with ic5: i_dur = st.selectbox("Διάρκεια Συμβολαίου", ["Ετήσιο", "Εξάμηνο", "Τρίμηνο", "Άλλο"])
                
                ic6, ic7, ic8 = st.columns(3)
                with ic6: i_prem = st.text_input("Ασφάλιστρο (€)", value="0")
                with ic7: i_build = st.text_input("Κεφάλαιο Κτιρίου (€)", value="0")
                with ic8: i_cont = st.text_input("Κεφάλαιο Περιεχομένου (€)", value="0")
                
                if st.form_submit_button("Αποθήκευση Ασφαλιστηρίου", use_container_width=True):
                    if i_comp and i_num:
                        try:
                            ins_id = f"INS-{uuid.uuid4().hex[:6].upper()}"
                            gsheets_service.add_insurance([ins_id, i_prop, i_cat, i_comp, i_num, i_date.strftime("%Y-%m-%d"), i_dur, i_prem, i_build, i_cont])
                            st.success("Το ασφαλιστήριο καταχωρήθηκε επιτυχώς!")
                        except Exception as e: st.error(f"Σφάλμα: {e}")
                    else: st.warning("Συμπληρώστε υποχρεωτικά την Εταιρεία και τον Αριθμό Συμβολαίου.")

    # ==========================================
    # 3. ΕΠΕΞΕΡΓΑΣΙΑ / ΔΙΑΓΡΑΦΗ
    # ==========================================
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

    with tab_ins_edit:
        if insurances_df.empty: st.warning("Δεν υπάρχουν ασφαλιστήρια.")
        else:
            prop_options = {row["Property_ID"]: f"{row.get('Χαρακτηριστικό', '')} ({row.get('Διεύθυνση', '')})" for _, row in properties_df.iterrows()}
            
            i_edit_opts = {}
            for _, r in insurances_df.iterrows():
                i_id = str(r.get("Insurance_ID", ""))
                c_comp = str(r.get("Company", ""))
                c_num = str(r.get("Contract_Number", ""))
                p_charact = properties_df[properties_df["Property_ID"] == str(r.get("Property_ID", ""))].iloc[0].get("Χαρακτηριστικό", "-") if not properties_df.empty and str(r.get("Property_ID", "")) in properties_df["Property_ID"].values else "-"
                i_edit_opts[i_id] = f"{c_comp} ({c_num}) | {p_charact}"
                
            selected_i_edit = st.selectbox("Επιλέξτε Ασφαλιστήριο προς επεξεργασία", options=list(i_edit_opts.keys()), format_func=lambda x: i_edit_opts[x])
            
            if selected_i_edit:
                sel_ins = insurances_df[insurances_df["Insurance_ID"] == selected_i_edit].iloc[0]
                
                with st.form("edit_insurance_form"):
                    curr_prop = str(sel_ins.get("Property_ID", ""))
                    p_keys = list(prop_options.keys())
                    try: p_idx = p_keys.index(curr_prop)
                    except: p_idx = 0
                    e_prop = st.selectbox("Ακίνητο *", p_keys, index=p_idx, format_func=lambda x: prop_options[x]) if p_keys else ""
                    
                    ic1, ic2 = st.columns(2)
                    c_opts = ["Ασφάλιση Πυρός / Σεισμού", "Αστική Ευθύνη", "Νομική Προστασία", "Άλλο"]
                    curr_cat = str(sel_ins.get("Category", ""))
                    with ic1: e_cat = st.selectbox("Κατηγορία Κινδύνου *", c_opts, index=c_opts.index(curr_cat) if curr_cat in c_opts else 0)
                    with ic2: e_comp = st.text_input("Ασφαλιστική Εταιρεία *", value=str(sel_ins.get("Company", "")).replace('nan',''))
                    
                    ic3, ic4, ic5 = st.columns(3)
                    with ic3: e_num = st.text_input("Αριθμός Συμβολαίου *", value=str(sel_ins.get("Contract_Number", "")).replace('nan',''))
                    try: ren_d = datetime.strptime(str(sel_ins.get("Renewal_Date", "")), "%Y-%m-%d").date()
                    except: ren_d = date.today()
                    with ic4: e_date = st.date_input("Ημ/νία Ανανέωσης (Επόμενη) *", value=ren_d)
                    
                    d_opts = ["Ετήσιο", "Εξάμηνο", "Τρίμηνο", "Άλλο"]
                    curr_dur = str(sel_ins.get("Duration", ""))
                    with ic5: e_dur = st.selectbox("Διάρκεια Συμβολαίου", d_opts, index=d_opts.index(curr_dur) if curr_dur in d_opts else 0)
                    
                    ic6, ic7, ic8 = st.columns(3)
                    with ic6: e_prem = st.text_input("Ασφάλιστρο (€)", value=str(sel_ins.get("Premium", "")).replace('.', ','))
                    with ic7: e_build = st.text_input("Κεφάλαιο Κτιρίου (€)", value=str(sel_ins.get("Insured_Building", "")).replace('.', ','))
                    with ic8: e_cont = st.text_input("Κεφάλαιο Περιεχομένου (€)", value=str(sel_ins.get("Insured_Contents", "")).replace('.', ','))
                    
                    upd_i_btn = st.form_submit_button("Αποθήκευση Αλλαγών", type="primary", use_container_width=True)
                    
                if st.button("🗑️ Οριστική Διαγραφή Ασφαλιστηρίου", use_container_width=True):
                    try:
                        gsheets_service.delete_insurance(selected_i_edit)
                        st.success("Το ασφαλιστήριο διαγράφηκε! Ανανεώστε τη σελίδα.")
                    except Exception as e: st.error(f"Σφάλμα: {e}")

                if upd_i_btn:
                    if e_comp and e_num:
                        try:
                            new_row = [selected_i_edit, e_prop, e_cat, e_comp, e_num, e_date.strftime("%Y-%m-%d"), e_dur, e_prem, e_build, e_cont]
                            gsheets_service.update_insurance(selected_i_edit, new_row)
                            st.success("Οι αλλαγές αποθηκεύτηκαν! Ανανεώστε τη σελίδα.")
                        except Exception as e: st.error(f"Σφάλμα επεξεργασίας: {e}")
                    else: st.warning("Συμπληρώστε υποχρεωτικά την Εταιρεία και τον Αριθμό Συμβολαίου.")
