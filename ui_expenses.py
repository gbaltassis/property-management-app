import streamlit as st
import gsheets_service
import uuid
import pandas as pd
import time
from datetime import date, datetime

COMMON_CSS = """
<style>
    .custom-table { width: 100% !important; border-collapse: collapse; font-family: sans-serif; font-size: 14px; margin-bottom: 2rem; }
    .custom-table th { text-align: left !important; background-color: #f0f2f6; padding: 12px; border-bottom: 1px solid #e6e9ef; color: #31333F; }
    .custom-table td { text-align: left !important; word-wrap: break-word !important; white-space: normal !important; padding: 12px; border-bottom: 1px solid #e6e9ef; color: #31333F; vertical-align: top; }
</style>
"""

def show():
    st.markdown(COMMON_CSS, unsafe_allow_html=True)
    st.header("Διαχείριση Εξόδων & Ζημιών")
    
    try:
        properties_df = gsheets_service.fetch_all_properties()
        expenses_df = gsheets_service.fetch_all_expenses()
    except Exception as e:
        st.error(f"Αδυναμία φόρτωσης δεδομένων: {e}")
        return

    owner_afms = set()
    prop_options = {}
    if not properties_df.empty:
        for _, p in properties_df.iterrows():
            prop_options[str(p.get("Property_ID", ""))] = f"{str(p.get('Χαρακτηριστικό', ''))} ({str(p.get('Διεύθυνση', ''))})"
            for i in range(1, 4):
                afm = str(p.get(f'AFM_{i}', '')).strip()
                if len(afm) == 8: afm = "0" + afm
                name = f"{str(p.get(f'Name_{i}', '')).strip()} {str(p.get(f'Surname_{i}', '')).strip()}".strip()
                if afm and afm != 'nan': owner_afms.add(f"{afm} - {name}")

    tab_list, tab_new, tab_edit = st.tabs(["📋 Ιστορικό Εξόδων", "➕ Νέο Έξοδο", "✏️ Επεξεργασία"])

    # --- 1. ΝΕΟ ΕΞΟΔΟ ---
    with tab_new:
        cat_opts = ["ΕΝΦΙΑ", "Ασφάλιση Πυρός", "Ασφάλιση Νομικής Προστασίας", "Ζημιά / Βλάβη", "Άλλο Έξοδο"]
        category = st.selectbox("Κατηγορία Εξόδου *", cat_opts, key="new_exp_cat")
        st.markdown("---")
        
        with st.form("new_expense_form", clear_on_submit=True):
            afm_sel, prop_sel = "", ""
            if category == "ΕΝΦΙΑ":
                afm_sel = st.selectbox("Ιδιοκτήτης (ΑΦΜ) *", list(owner_afms)) if owner_afms else st.text_input("ΑΦΜ Ιδιοκτήτη *")
            else:
                prop_sel = st.selectbox("Ακίνητο *", list(prop_options.keys()), format_func=lambda x: prop_options[x]) if prop_options else ""

            ec1, ec2 = st.columns(2)
            amount, enfia_main, enfia_sur = "0", "0", "0"
            date_paid = date.today()
            
            # --- ΝΕΑ ΛΟΓΙΚΗ ΓΙΑ ΤΟΝ ΕΝΦΙΑ ---
            if category == "ΕΝΦΙΑ":
                with ec1: enfia_main = st.text_input("Συνολικός Κύριος Φόρος (€) *", value="0")
                with ec2: enfia_sur = st.text_input("Συνολική Έκπτωση / Προσαύξηση (€)", value="0", help="Βάλε μείον (-) αν είναι έκπτωση")
                date_paid = st.date_input("Ημ/νία Πληρωμής / Έκδοσης *", value=date.today())
            else:
                with ec1: amount = st.text_input("Ποσό (€) *", value="0")
                with ec2: date_paid = st.date_input("Ημ/νία Πληρωμής *", value=date.today())

            desc, detailed_desc, ins_comp, contract_num, ren_date, dur, ins_build, ins_cont = "", "", "", "", "", "", "", ""
            
            if category in ["Ζημιά / Βλάβη", "Άλλο Έξοδο"]:
                desc = st.text_input("Περιγραφή (π.χ. Κηπουρός) *")
                detailed_desc = st.text_area("Αναλυτική Περιγραφή (π.χ. Τι ακριβώς επισκευάστηκε)")
            
            if "Ασφάλιση" in category:
                sc1, sc2, sc3, sc4 = st.columns(4)
                with sc1: ins_comp = st.text_input("Ασφαλιστική Εταιρεία *")
                with sc2: contract_num = st.text_input("Αριθμός Συμβολαίου")
                with sc3: ren_date = st.date_input("Ημ/νία Ανανέωσης (Επόμενη) *")
                with sc4: dur = st.selectbox("Διάρκεια Συμβολαίου", ["Ετήσιο", "Εξάμηνο", "Τρίμηνο", "Άλλο"])
                if category == "Ασφάλιση Πυρός":
                    bc1, bc2 = st.columns(2)
                    with bc1: ins_build = st.text_input("Κεφάλαιο Κτιρίου (€)", value="0")
                    with bc2: ins_cont = st.text_input("Κεφάλαιο Περιεχομένου (€)", value="0")

            if st.form_submit_button("Αποθήκευση Εξόδου", type="primary", use_container_width=True):
                if category == "ΕΝΦΙΑ":
                    m_val = pd.to_numeric(enfia_main.replace(',', '.'), errors='coerce')
                    s_val = pd.to_numeric(enfia_sur.replace(',', '.'), errors='coerce')
                    if pd.isna(m_val): m_val = 0.0
                    if pd.isna(s_val): s_val = 0.0
                    amt_val = m_val + s_val
                    amount = str(amt_val).replace('.', ',')
                else:
                    amt_val = pd.to_numeric(amount.replace(',', '.'), errors='coerce')

                if pd.isna(amt_val) or amt_val <= 0:
                    st.warning("Παρακαλώ εισάγετε έγκυρο ποσό.")
                else:
                    exp_id = f"EXP-{uuid.uuid4().hex[:6].upper()}"
                    final_afm = afm_sel.split(" - ")[0] if " - " in afm_sel else afm_sel
                    r_date_str = ren_date.strftime("%Y-%m-%d") if ren_date else ""
                    
                    # Προσθήκη των νέων πεδίων (enfia_main, enfia_sur) στο row
                    row = [exp_id, category, prop_sel, final_afm, amount, date_paid.strftime("%Y-%m-%d"), desc, ins_comp, r_date_str, dur, ins_build, ins_cont, contract_num, detailed_desc, enfia_main, enfia_sur]
                    try:
                        gsheets_service.add_expense(row)
                        st.success("Το έξοδο καταχωρήθηκε επιτυχώς!")
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e: st.error(f"Σφάλμα: {e}")

    # --- 2. ΙΣΤΟΡΙΚΟ ---
    with tab_list:
        if expenses_df.empty: st.info("Δεν έχουν καταγραφεί έξοδα.")
        else:
            exp_list = []
            for _, r in expenses_df.iterrows():
                amt = pd.to_numeric(str(r.get('Amount', '0')).replace(',', '.'), errors='coerce')
                if pd.isna(amt): amt = 0.0
                
                cat = str(r.get("Category", ""))
                target = str(r.get("AFM", "")) if cat == "ΕΝΦΙΑ" else prop_options.get(str(r.get("Property_ID", "")), "-")
                
                details = str(r.get("Description", "")).replace('nan', '')
                if "Ασφάλιση" in cat:
                    ins_comp = str(r.get('Insurance_Company', '')).replace('nan', '')
                    contract = str(r.get('Contract_Number', '')).replace('nan', '')
                    ren_date = str(r.get('Renewal_Date', '')).replace('nan', '')
                    details = f"<b>{ins_comp}</b>"
                    if contract: details += f" (Συμβ: {contract})"
                    if ren_date: details += f"<br><span style='font-size: 12px; color: #555;'>Ανανέωση: {ren_date}</span>"
                elif cat == "ΕΝΦΙΑ":
                    e_m = pd.to_numeric(str(r.get('ENFIA_Main_Tax', '0')).replace(',', '.'), errors='coerce')
                    e_s = pd.to_numeric(str(r.get('ENFIA_Surcharge', '0')).replace(',', '.'), errors='coerce')
                    details = f"Κύριος Φόρος: {e_m:.2f}€ | Προσ/ξηση: {e_s:.2f}€"
                elif cat in ["Ζημιά / Βλάβη", "Άλλο Έξοδο"]:
                    det_desc = str(r.get("Detailed_Description", "")).replace('nan', '')
                    if det_desc: details = f"<b>{details}</b><br><span style='font-size: 12px; color: #555;'>{det_desc}</span>"
                
                exp_list.append({
                    "Ημερομηνία": str(r.get("Date_Paid", "")),
                    "Κατηγορία": cat,
                    "Αφορά": target,
                    "Ποσό": f"{amt:.2f} €".replace('.', ','),
                    "Λεπτομέρειες": details
                })
            html_table = pd.DataFrame(exp_list[::-1]).to_html(classes='custom-table', escape=False, index=False, justify='left')
            st.write(f'<div style="overflow-x: auto; max-width: 100%;">{html_table}</div>', unsafe_allow_html=True)

    # --- 3. ΕΠΕΞΕΡΓΑΣΙΑ / ΔΙΑΓΡΑΦΗ ---
    with tab_edit:
        if expenses_df.empty: st.warning("Δεν υπάρχουν έξοδα.")
        else:
            e_opts = {}
            for _, r in expenses_df.iterrows():
                exp_id_val = str(r.get("Expense_ID", ""))
                cat_val = str(r.get("Category", ""))
                date_paid_val = str(r.get("Date_Paid", ""))
                target_val = str(r.get("AFM", "")) if cat_val == "ΕΝΦΙΑ" else prop_options.get(str(r.get("Property_ID", "")), "-")
                
                extra_info = ""
                if "Ασφάλιση" in cat_val:
                    contract = str(r.get("Contract_Number", "")).replace('nan', '')
                    if contract: extra_info = f" | Συμβ: {contract}"
                elif cat_val in ["Ζημιά / Βλάβη", "Άλλο Έξοδο"]:
                    desc = str(r.get("Description", "")).replace('nan', '')
                    det_desc = str(r.get("Detailed_Description", "")).replace('nan', '')
                    if det_desc: desc = f"{desc} ({det_desc})"
                    if desc: extra_info = f" | {desc[:40] + '...' if len(desc) > 40 else desc}"
                
                e_opts[exp_id_val] = f"{date_paid_val} | {cat_val} | {target_val}{extra_info}"
                
            sel_exp = st.selectbox("Επιλέξτε Έξοδο προς επεξεργασία", options=list(e_opts.keys()), format_func=lambda x: e_opts[x])
            
            if sel_exp:
                sel_row = expenses_df[expenses_df["Expense_ID"] == sel_exp].iloc[0]
                
                cat_opts = ["ΕΝΦΙΑ", "Ασφάλιση Πυρός", "Ασφάλιση Νομικής Προστασίας", "Ζημιά / Βλάβη", "Άλλο Έξοδο"]
                curr_cat = str(sel_row.get("Category", "")).strip()
                
                if f"edit_exp_cat_state" not in st.session_state or st.session_state.get("last_sel_exp") != sel_exp:
                    st.session_state["edit_exp_cat_state"] = curr_cat
                    st.session_state["last_sel_exp"] = sel_exp

                e_category = st.selectbox("Κατηγορία Εξόδου *", cat_opts, key="edit_exp_cat_state")
                st.markdown("---")
                
                with st.form("edit_expense_form"):
                    afm_sel, prop_sel = "", ""
                    if e_category == "ΕΝΦΙΑ":
                        curr_afm = str(sel_row.get("AFM", ""))
                        afm_opts = list(owner_afms)
                        afm_idx = 0
                        for i, a in enumerate(afm_opts):
                            if curr_afm in a: afm_idx = i
                        afm_sel = st.selectbox("Ιδιοκτήτης (ΑΦΜ) *", afm_opts, index=afm_idx) if afm_opts else st.text_input("ΑΦΜ Ιδιοκτήτη *", value=curr_afm)
                    else:
                        curr_prop = str(sel_row.get("Property_ID", ""))
                        p_keys = list(prop_options.keys())
                        try: p_idx = p_keys.index(curr_prop)
                        except: p_idx = 0
                        prop_sel = st.selectbox("Ακίνητο *", p_keys, index=p_idx, format_func=lambda x: prop_options[x]) if p_keys else ""

                    ec1, ec2 = st.columns(2)
                    amount, enfia_main, enfia_sur = "0", "0", "0"
                    
                    try: pay_date = datetime.strptime(str(sel_row.get("Date_Paid", "")), "%Y-%m-%d").date()
                    except: pay_date = date.today()
                    
                    if e_category == "ΕΝΦΙΑ":
                        with ec1: enfia_main = st.text_input("Συνολικός Κύριος Φόρος (€) *", value=str(sel_row.get("ENFIA_Main_Tax", "")).replace('.', ','))
                        with ec2: enfia_sur = st.text_input("Συνολική Έκπτωση / Προσαύξηση (€)", value=str(sel_row.get("ENFIA_Surcharge", "")).replace('.', ','))
                        date_paid = st.date_input("Ημ/νία Πληρωμής / Έκδοσης *", value=pay_date)
                    else:
                        with ec1: amount = st.text_input("Ποσό (€) *", value=str(sel_row.get("Amount", "")).replace('.', ','))
                        with ec2: date_paid = st.date_input("Ημ/νία Πληρωμής *", value=pay_date)

                    desc, detailed_desc, ins_comp, contract_num, ren_date, dur, ins_build, ins_cont = "", "", "", "", "", "", "", ""
                    
                    if e_category in ["Ζημιά / Βλάβη", "Άλλο Έξοδο"]:
                        desc = st.text_input("Περιγραφή (π.χ. Κηπουρός) *", value=str(sel_row.get("Description", "")).replace('nan',''))
                        detailed_desc = st.text_area("Αναλυτική Περιγραφή", value=str(sel_row.get("Detailed_Description", "")).replace('nan',''))
                    
                    if "Ασφάλιση" in e_category:
                        sc1, sc2, sc3, sc4 = st.columns(4)
                        with sc1: ins_comp = st.text_input("Ασφαλιστική Εταιρεία *", value=str(sel_row.get("Insurance_Company", "")).replace('nan',''))
                        with sc2: contract_num = st.text_input("Αριθμός Συμβολαίου", value=str(sel_row.get("Contract_Number", "")).replace('nan',''))
                        try: r_date = datetime.strptime(str(sel_row.get("Renewal_Date", "")), "%Y-%m-%d").date()
                        except: r_date = date.today()
                        with sc3: ren_date = st.date_input("Ημ/νία Ανανέωσης (Επόμενη) *", value=r_date)
                        dur_opts = ["Ετήσιο", "Εξάμηνο", "Τρίμηνο", "Άλλο"]
                        curr_dur = str(sel_row.get("Duration_Months", ""))
                        with sc4: dur = st.selectbox("Διάρκεια Συμβολαίου", dur_opts, index=dur_opts.index(curr_dur) if curr_dur in dur_opts else 0)
                        if e_category == "Ασφάλιση Πυρός":
                            bc1, bc2 = st.columns(2)
                            with bc1: ins_build = st.text_input("Κεφάλαιο Κτιρίου (€)", value=str(sel_row.get("Insured_Building", "")).replace('.', ','))
                            with bc2: ins_cont = st.text_input("Κεφάλαιο Περιεχομένου (€)", value=str(sel_row.get("Insured_Contents", "")).replace('.', ','))

                    upd_btn = st.form_submit_button("Αποθήκευση Αλλαγών", type="primary", use_container_width=True)
                    
                if st.button("🗑️ Οριστική Διαγραφή Εξόδου", use_container_width=True):
                    try:
                        gsheets_service.delete_expense(sel_exp)
                        st.success("Διαγράφηκε! Η σελίδα ανανεώνεται...")
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e: st.error(f"Σφάλμα: {e}")

                if upd_btn:
                    if e_category == "ΕΝΦΙΑ":
                        m_val = pd.to_numeric(enfia_main.replace(',', '.'), errors='coerce')
                        s_val = pd.to_numeric(enfia_sur.replace(',', '.'), errors='coerce')
                        if pd.isna(m_val): m_val = 0.0
                        if pd.isna(s_val): s_val = 0.0
                        amt_val = m_val + s_val
                        amount = str(amt_val).replace('.', ',')
                    else:
                        amt_val = pd.to_numeric(amount.replace(',', '.'), errors='coerce')

                    if pd.isna(amt_val) or amt_val <= 0:
                        st.warning("Παρακαλώ εισάγετε έγκυρο ποσό.")
                    else:
                        final_afm = afm_sel.split(" - ")[0] if " - " in afm_sel else afm_sel
                        r_date_str = ren_date.strftime("%Y-%m-%d") if ren_date else ""
                        new_row = [sel_exp, e_category, prop_sel, final_afm, amount, date_paid.strftime("%Y-%m-%d"), desc, ins_comp, r_date_str, dur, ins_build, ins_cont, contract_num, detailed_desc, enfia_main, enfia_sur]
                        try:
                            gsheets_service.update_expense(sel_exp, new_row)
                            st.success("Οι αλλαγές αποθηκεύτηκαν!")
                            time.sleep(1.5)
                            st.rerun()
                        except Exception as e: st.error(f"Σφάλμα επεξεργασίας: {e}")
