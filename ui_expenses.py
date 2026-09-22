import streamlit as st
import gsheets_service
import uuid
import pandas as pd
import time
import json
from datetime import date, datetime
import streamlit.components.v1 as components

COMMON_CSS = """
<style>
    html, body { font-family: sans-serif; }
    .table-container { height: 550px; overflow-y: auto; overflow-x: auto; border: 1px solid #ddd; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 20px; }
    .custom-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 12px; background: white; min-width: 600px; }
    .custom-table th, .custom-table td { padding: 6px 8px; border-bottom: 1px solid #e6e9ef; border-right: 1px solid #e6e9ef; text-align: left; vertical-align: middle; line-height: 1.2; }
    .custom-table th { background-color: #f0f2f6; color: #31333F; position: sticky; top: 0; z-index: 4; box-shadow: 0 1px 0 #ddd; cursor: pointer; user-select: none; transition: background-color 0.2s;}
    .custom-table th:hover { background-color: #e2e6ea; }
    .custom-table th:first-child, .custom-table td:first-child { position: sticky; left: 0; z-index: 3; background-color: #ffffff; box-shadow: 1px 0 0 #ddd; font-weight: 600; min-width: 90px; max-width: 140px; white-space: normal !important; word-wrap: break-word; }
    .custom-table th:first-child { z-index: 5; background-color: #f0f2f6; box-shadow: 1px 1px 0 #ddd; }
    .action-btn { display: block; width: 100%; background-color: #f8f9fa; border: 1px solid #ddd; padding: 4px; border-radius: 4px; cursor: pointer; color: #31333F; font-size: 11px; font-weight: bold; transition: 0.2s; text-align: center; }
    .action-btn:hover { background-color: #e2e6ea; border-color: #dae0e5; }
    @media (prefers-color-scheme: dark) {
        .table-container { border-color: #444; }
        .custom-table { background: #0e1117; color: white; }
        .custom-table th { background-color: #262730; color: white; box-shadow: 0 1px 0 #444; }
        .custom-table th:hover { background-color: #383a45; }
        .custom-table th:first-child, .custom-table td:first-child { background-color: #0e1117; box-shadow: 1px 0 0 #666; color: white; }
        .custom-table th:first-child { background-color: #262730; box-shadow: 1px 1px 0 #666; }
        .custom-table td { border-color: #444; }
        .action-btn { background-color: #1e2127; border-color: #444; color: #ddd; }
    }
</style>
"""

COMMON_JS = """
<script>
    function sortTable(tableId, n) {
        var table, rows, switching, i, x, y, shouldSwitch, dir, switchcount = 0;
        table = document.getElementById(tableId);
        switching = true;
        dir = "asc"; 
        while (switching) {
            switching = false;
            rows = table.getElementsByTagName("TR");
            for (i = 1; i < (rows.length - 1); i++) {
                shouldSwitch = false;
                x = rows[i].getElementsByTagName("TD")[n];
                y = rows[i + 1].getElementsByTagName("TD")[n];
                if(!x || !y) continue;
                let valX = x.innerText.trim().toLowerCase();
                let valY = y.innerText.trim().toLowerCase();
                if(valX.includes('€')) valX = parseFloat(valX.replace(/[^0-9,-]/g, '').replace(',', '.'));
                if(valY.includes('€')) valY = parseFloat(valY.replace(/[^0-9,-]/g, '').replace(',', '.'));
                if(valX.match(/^\\d{4}-\\d{2}-\\d{2}/)) valX = new Date(valX).getTime();
                if(valY.match(/^\\d{4}-\\d{2}-\\d{2}/)) valY = new Date(valY).getTime();
                if (dir == "asc") {
                    if (valX > valY) { shouldSwitch = true; break; }
                } else if (dir == "desc") {
                    if (valX < valY) { shouldSwitch = true; break; }
                }
            }
            if (shouldSwitch) {
                rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);
                switching = true;
                switchcount ++;      
            } else {
                if (switchcount == 0 && dir == "asc") { dir = "desc"; switching = true; }
            }
        }
    }

    (function hideInput() {
        var pDoc = window.parent.document;
        var inputs = pDoc.querySelectorAll('input[aria-label="hidden_exp_click"]');
        if (inputs.length > 0) {
            inputs.forEach(function(input) {
                var wrapper = input.closest('div[data-testid="stTextInput"]');
                if (wrapper) { wrapper.style.position = 'absolute'; wrapper.style.opacity = '0'; wrapper.style.pointerEvents = 'none'; wrapper.style.height = '0px'; wrapper.style.overflow = 'hidden'; }
            });
        } else { setTimeout(hideInput, 100); }
    })();

    function triggerPython(action_val) {
        var payload = action_val + '|' + Date.now();
        var pDoc = window.parent.document;
        var input = pDoc.querySelector('input[aria-label="hidden_exp_click"]');
        if(input) {
            var nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            nativeSetter.call(input, payload);
            input.dispatchEvent(new Event('input', {bubbles: true}));
            input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', keyCode: 13, which: 13, bubbles: true}));
        }
    }
</script>
"""

def handle_expense_action():
    key_name = st.session_state.current_exp_hidden_key
    val = st.session_state.get(key_name, "")
    if val:
        parts = val.split('|')
        action = parts[0]
        if action.startswith("EDIT_"):
            st.session_state.expense_action = 'edit'
            st.session_state.action_exp_id = action.replace("EDIT_", "")
        st.session_state[key_name] = ""

def show():
    if "expense_action" not in st.session_state:
        st.session_state.expense_action = None
    if "action_exp_id" not in st.session_state:
        st.session_state.action_exp_id = None

    if "current_exp_hidden_key" not in st.session_state:
        st.session_state.current_exp_hidden_key = f"hidden_exp_click_val_{uuid.uuid4().hex[:8]}"

    st.text_input("hidden_exp_click", key=st.session_state.current_exp_hidden_key, label_visibility="collapsed", on_change=handle_expense_action)
    st.markdown(COMMON_CSS, unsafe_allow_html=True)
    
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

    st.header("Διαχείριση Εξόδων & Ζημιών")

    if st.session_state.expense_action == 'new':
        st.markdown("### ➕ Προσθήκη Νέου Εξόδου")
        col_back, _ = st.columns([1, 4])
        if col_back.button("⬅️ Επιστροφή", use_container_width=True, key="back_btn_exp_new"):
            st.session_state.expense_action = None
            st.rerun()

        cat_opts = ["ΕΝΦΙΑ", "Ασφάλιση Πυρός", "Ασφάλιση Νομικής Προστασίας", "Ζημιά / Βλάβη", "Άλλο Έξοδο"]
        category = st.selectbox("Κατηγορία Εξόδου *", cat_opts, key="new_exp_cat_sel")
        st.markdown("---")
        
        with st.form("new_expense_form", clear_on_submit=True):
            afm_sel, prop_sel = "", ""
            if category == "ΕΝΦΙΑ":
                afm_sel = st.selectbox("Ιδιοκτήτης (ΑΦΜ) *", list(owner_afms), key="new_exp_afm_sel") if owner_afms else st.text_input("ΑΦΜ Ιδιοκτήτη *", key="new_exp_afm_txt")
            else:
                prop_sel = st.selectbox("Ακίνητο *", list(prop_options.keys()), format_func=lambda x: prop_options[x], key="new_exp_prop_sel") if prop_options else ""

            amount, enfia_sur = "0", "0"
            enfia_breakdown = {}
            date_paid = date.today()
            
            if category == "ΕΝΦΙΑ":
                final_afm = afm_sel.split(" - ")[0] if " - " in afm_sel else afm_sel
                st.write("**Επιμερισμός Κύριου Φόρου ανά Ακίνητο (βάσει Εκκαθαριστικού):**")
                
                owned_props = []
                if not properties_df.empty:
                    for _, p in properties_df.iterrows():
                        for i in range(1, 4):
                            a = str(p.get(f'AFM_{i}', '')).strip()
                            if len(a) == 8: a = "0" + a
                            if a == final_afm:
                                perc = pd.to_numeric(str(p.get(f'Perc_{i}', '0')).replace(',', '.'), errors='coerce')
                                if perc > 0: owned_props.append((str(p.get("Property_ID", "")), str(p.get("Χαρακτηριστικό", "-"))))
                                break
                
                if not owned_props:
                    st.info("Δεν βρέθηκαν ακίνητα για αυτό το ΑΦΜ στο Μητρώο.")
                else:
                    for pid, pchar in owned_props:
                        val = st.text_input(f"Κύριος Φόρος: {pchar} (€)", value="0", key=f"new_enf_main_{pid}")
                        enfia_breakdown[pid] = val
                
                st.markdown("---")
                enfia_sur = st.text_input("Συνολική Έκπτωση / Προσαύξηση (€)", value="0", help="Βάλε μείον (-) αν είναι έκπτωση", key="new_exp_enf_sur")
                date_paid = st.date_input("Ημ/νία Πληρωμής / Έκδοσης *", value=date.today(), key="new_exp_enf_d")
            else:
                ec1, ec2 = st.columns(2)
                with ec1: amount = st.text_input("Ποσό (€) *", value="0", key="new_exp_amt")
                with ec2: date_paid = st.date_input("Ημ/νία Πληρωμής *", value=date.today(), key="new_exp_d")

            desc, detailed_desc, ins_comp, contract_num, dur, ins_build, ins_cont = "", "", "", "", "", "", ""
            
            if category in ["Ζημιά / Βλάβη", "Άλλο Έξοδο"]:
                desc = st.text_input("Περιγραφή (π.χ. Κηπουρός) *", key="new_exp_desc")
                detailed_desc = st.text_area("Αναλυτική Περιγραφή (π.χ. Τι ακριβώς επισκευάστηκε)", key="new_exp_det_desc")
            
            if "Ασφάλιση" in category:
                sc1, sc2, sc3 = st.columns(3)
                with sc1: ins_comp = st.text_input("Ασφαλιστική Εταιρεία *", key="new_exp_ins")
                with sc2: contract_num = st.text_input("Αριθμός Συμβολαίου", key="new_exp_cont")
                with sc3: dur = st.selectbox("Διάρκεια Συμβολαίου", ["Ετήσιο", "Εξάμηνο", "Τρίμηνο", "Άλλο"], key="new_exp_dur")

            if st.form_submit_button("Αποθήκευση Εξόδου", type="primary", use_container_width=True):
                enfia_breakdown_str = "{}"
                if category == "ΕΝΦΙΑ":
                    total_main = 0.0
                    clean_dict = {}
                    for pid, val in enfia_breakdown.items():
                        num = pd.to_numeric(val.replace(',', '.'), errors='coerce')
                        if pd.isna(num): num = 0.0
                        clean_dict[pid] = num
                        total_main += num
                    s_val = pd.to_numeric(enfia_sur.replace(',', '.'), errors='coerce')
                    if pd.isna(s_val): s_val = 0.0
                    amt_val = total_main + s_val
                    amount = str(amt_val).replace('.', ',')
                    enfia_breakdown_str = json.dumps(clean_dict)
                else:
                    amt_val = pd.to_numeric(amount.replace(',', '.'), errors='coerce')

                if pd.isna(amt_val) or amt_val <= 0:
                    st.warning("Παρακαλώ εισάγετε έγκυρο ποσό (ή ελέγξτε τα ποσά του ΕΝΦΙΑ).")
                else:
                    exp_id = f"EXP-{uuid.uuid4().hex[:6].upper()}"
                    final_afm = afm_sel.split(" - ")[0] if " - " in afm_sel else afm_sel
                    r_date_str = ""
                    
                    row = [exp_id, category, prop_sel, final_afm, amount, date_paid.strftime("%Y-%m-%d"), desc, ins_comp, r_date_str, dur, ins_build, ins_cont, contract_num, detailed_desc, enfia_breakdown_str, enfia_sur]
                    try:
                        gsheets_service.add_expense(row)
                        st.success("Το έξοδο καταχωρήθηκε επιτυχώς!")
                        time.sleep(1.5)
                        st.session_state.expense_action = None
                        st.rerun()
                    except Exception as e: st.error(f"Σφάλμα: {e}")

    elif st.session_state.expense_action == 'edit':
        st.markdown("### ✏️ Επεξεργασία Εγγραφής")
        col_back, _ = st.columns([1, 4])
        if col_back.button("⬅️ Επιστροφή", use_container_width=True, key="back_btn_exp_edit"):
            st.session_state.expense_action = None
            st.rerun()

        sel_exp = st.session_state.action_exp_id
        sel_row = expenses_df[expenses_df["Expense_ID"] == sel_exp].iloc[0]
        
        cat_opts = ["ΕΝΦΙΑ", "Ασφάλιση Πυρός", "Ασφάλιση Νομικής Προστασίας", "Ζημιά / Βλάβη", "Άλλο Έξοδο"]
        curr_cat = str(sel_row.get("Category", "")).strip()
        
        if f"edit_exp_cat_state_{sel_exp}" not in st.session_state or st.session_state.get("last_sel_exp") != sel_exp:
            st.session_state[f"edit_exp_cat_state_{sel_exp}"] = curr_cat
            st.session_state["last_sel_exp"] = sel_exp

        e_category = st.selectbox("Κατηγορία Εξόδου *", cat_opts, key=f"edit_exp_cat_state_{sel_exp}")
        st.markdown("---")
        
        with st.form("edit_expense_form"):
            afm_sel, prop_sel = "", ""
            if e_category == "ΕΝΦΙΑ":
                curr_afm = str(sel_row.get("AFM", ""))
                afm_opts = list(owner_afms)
                afm_idx = 0
                for i, a in enumerate(afm_opts):
                    if curr_afm in a: afm_idx = i
                afm_sel = st.selectbox("Ιδιοκτήτης (ΑΦΜ) *", afm_opts, index=afm_idx, key=f"e_afm_{sel_exp}") if afm_opts else st.text_input("ΑΦΜ Ιδιοκτήτη *", value=curr_afm, key=f"e_afmtxt_{sel_exp}")
            else:
                curr_prop = str(sel_row.get("Property_ID", ""))
                p_keys = list(prop_options.keys())
                try: p_idx = p_keys.index(curr_prop)
                except: p_idx = 0
                prop_sel = st.selectbox("Ακίνητο *", p_keys, index=p_idx, format_func=lambda x: prop_options[x], key=f"e_prop_{sel_exp}") if p_keys else ""

            amount, enfia_sur = "0", "0"
            enfia_breakdown = {}
            try: pay_date = datetime.strptime(str(sel_row.get("Date_Paid", "")), "%Y-%m-%d").date()
            except: pay_date = date.today()
            
            if e_category == "ΕΝΦΙΑ":
                final_afm = afm_sel.split(" - ")[0] if " - " in afm_sel else afm_sel
                st.write("**Επιμερισμός Κύριου Φόρου ανά Ακίνητο:**")
                
                try: saved_breakdown = json.loads(str(sel_row.get("ENFIA_Breakdown", "{}")).replace('nan', '{}'))
                except: saved_breakdown = {}
                
                owned_props = []
                if not properties_df.empty:
                    for _, p in properties_df.iterrows():
                        for i in range(1, 4):
                            a = str(p.get(f'AFM_{i}', '')).strip()
                            if len(a) == 8: a = "0" + a
                            if a == final_afm:
                                perc = pd.to_numeric(str(p.get(f'Perc_{i}', '0')).replace(',', '.'), errors='coerce')
                                if perc > 0: owned_props.append((str(p.get("Property_ID", "")), str(p.get("Χαρακτηριστικό", "-"))))
                                break
                                
                for pid, pchar in owned_props:
                    old_val = str(saved_breakdown.get(pid, "0")).replace('.', ',')
                    val = st.text_input(f"Κύριος Φόρος: {pchar} (€)", value=old_val, key=f"e_enf_{pid}_{sel_exp}")
                    enfia_breakdown[pid] = val
                    
                st.markdown("---")
                enfia_sur = st.text_input("Συνολική Έκπτωση / Προσαύξηση (€)", value=str(sel_row.get("ENFIA_Surcharge", "")).replace('.', ','), key=f"e_enf_sur_{sel_exp}")
                date_paid = st.date_input("Ημ/νία Πληρωμής / Έκδοσης *", value=pay_date, key=f"e_enf_d_{sel_exp}")
            else:
                ec1, ec2 = st.columns(2)
                with ec1: amount = st.text_input("Ποσό (€) *", value=str(sel_row.get("Amount", "")).replace('.', ','), key=f"e_amt_{sel_exp}")
                with ec2: date_paid = st.date_input("Ημ/νία Πληρωμής *", value=pay_date, key=f"e_d_{sel_exp}")

            desc, detailed_desc, ins_comp, contract_num, dur, ins_build, ins_cont = "", "", "", "", "", "", ""
            
            if e_category in ["Ζημιά / Βλάβη", "Άλλο Έξοδο"]:
                desc = st.text_input("Περιγραφή (π.χ. Κηπουρός) *", value=str(sel_row.get("Description", "")).replace('nan',''), key=f"e_desc_{sel_exp}")
                detailed_desc = st.text_area("Αναλυτική Περιγραφή", value=str(sel_row.get("Detailed_Description", "")).replace('nan',''), key=f"e_detdesc_{sel_exp}")
            
            if "Ασφάλιση" in e_category:
                sc1, sc2, sc3 = st.columns(3)
                with sc1: ins_comp = st.text_input("Ασφαλιστική Εταιρεία *", value=str(sel_row.get("Insurance_Company", "")).replace('nan',''), key=f"e_ins_{sel_exp}")
                with sc2: contract_num = st.text_input("Αριθμός Συμβολαίου", value=str(sel_row.get("Contract_Number", "")).replace('nan',''), key=f"e_cont_{sel_exp}")
                dur_opts = ["Ετήσιο", "Εξάμηνο", "Τρίμηνο", "Άλλο"]
                curr_dur = str(sel_row.get("Duration_Months", ""))
                with sc3: dur = st.selectbox("Διάρκεια Συμβολαίου", dur_opts, index=dur_opts.index(curr_dur) if curr_dur in dur_opts else 0, key=f"e_dur_{sel_exp}")

            upd_btn = st.form_submit_button("Αποθήκευση Αλλαγών", type="primary", use_container_width=True)
            
        if st.button("🗑️ Οριστική Διαγραφή Εξόδου", use_container_width=True, key=f"del_{sel_exp}"):
            try:
                gsheets_service.delete_expense(sel_exp)
                st.success("Διαγράφηκε! Η σελίδα ανανεώνεται...")
                time.sleep(1.5)
                st.session_state.expense_action = None
                st.rerun()
            except Exception as e: st.error(f"Σφάλμα: {e}")

        if upd_btn:
            enfia_breakdown_str = "{}"
            if e_category == "ΕΝΦΙΑ":
                total_main = 0.0
                clean_dict = {}
                for pid, val in enfia_breakdown.items():
                    num = pd.to_numeric(val.replace(',', '.'), errors='coerce')
                    if pd.isna(num): num = 0.0
                    clean_dict[pid] = num
                    total_main += num
                s_val = pd.to_numeric(enfia_sur.replace(',', '.'), errors='coerce')
                if pd.isna(s_val): s_val = 0.0
                amt_val = total_main + s_val
                amount = str(amt_val).replace('.', ',')
                enfia_breakdown_str = json.dumps(clean_dict)
            else:
                amt_val = pd.to_numeric(amount.replace(',', '.'), errors='coerce')

            if pd.isna(amt_val) or amt_val <= 0:
                st.warning("Παρακαλώ εισάγετε έγκυρο ποσό.")
            else:
                final_afm = afm_sel.split(" - ")[0] if " - " in afm_sel else afm_sel
                r_date_str = "" 
                new_row = [sel_exp, e_category, prop_sel, final_afm, amount, date_paid.strftime("%Y-%m-%d"), desc, ins_comp, r_date_str, dur, ins_build, ins_cont, contract_num, detailed_desc, enfia_breakdown_str, enfia_sur]
                try:
                    gsheets_service.update_expense(sel_exp, new_row)
                    st.success("Οι αλλαγές αποθηκεύτηκαν!")
                    time.sleep(1.5)
                    st.session_state.expense_action = None
                    st.rerun()
                except Exception as e: st.error(f"Σφάλμα επεξεργασίας: {e}")

    else:
        st.caption("Ιστορικό Εξόδων & Ζημιών")
        if expenses_df.empty: 
            st.info("Δεν έχουν καταγραφεί έξοδα.")
        else:
            fc1, fc2 = st.columns(2)
            
            all_years = set()
            for _, r in expenses_df.iterrows():
                try: 
                    d = datetime.strptime(str(r.get("Date_Paid", "")), "%Y-%m-%d").date()
                    all_years.add(str(d.year))
                except: pass
            sorted_years = ["Όλα τα έτη"] + sorted(list(all_years), reverse=True)
            sel_year = fc1.selectbox("Επιλογή Έτους", sorted_years, key="filter_exp_year")

            all_cats = ["Όλες οι κατηγορίες", "ΕΝΦΙΑ", "Ασφάλιση Πυρός", "Ασφάλιση Νομικής Προστασίας", "Ζημιά / Βλάβη", "Άλλο Έξοδο"]
            sel_cat = fc2.selectbox("Κατηγορία", all_cats, key="filter_exp_cat")
            
            st.write("") 

            exp_list = []
            for _, r in expenses_df.iterrows():
                cat = str(r.get("Category", ""))
                if sel_cat != "Όλες οι κατηγορίες" and cat != sel_cat: continue
                
                raw_date = str(r.get("Date_Paid", ""))
                try: row_year = str(datetime.strptime(raw_date, "%Y-%m-%d").date().year)
                except: row_year = ""
                if sel_year != "Όλα τα έτη" and row_year != sel_year: continue

                amt = pd.to_numeric(str(r.get('Amount', '0')).replace(',', '.'), errors='coerce')
                if pd.isna(amt): amt = 0.0
                
                target = str(r.get("AFM", "")) if cat == "ΕΝΦΙΑ" else prop_options.get(str(r.get("Property_ID", "")), "-")
                
                details = str(r.get("Description", "")).replace('nan', '')
                if "Ασφάλιση" in cat:
                    ins_comp = str(r.get('Insurance_Company', '')).replace('nan', '')
                    contract = str(r.get('Contract_Number', '')).replace('nan', '')
                    details = f"<b>{ins_comp}</b>"
                    if contract: details += f" (Συμβ: {contract})"
                elif cat == "ΕΝΦΙΑ":
                    e_s = pd.to_numeric(str(r.get('ENFIA_Surcharge', '0')).replace(',', '.'), errors='coerce')
                    details = f"Αναλυτικός Φόρος<br><span style='font-size: 11px; color: #555;'>(Προσ/ξηση: {e_s:.2f}€)</span>"
                elif cat in ["Ζημιά / Βλάβη", "Άλλο Έξοδο"]:
                    det_desc = str(r.get("Detailed_Description", "")).replace('nan', '')
                    if det_desc: details = f"<b>{details}</b><br><span style='font-size: 11px; color: #555;'>{det_desc}</span>"
                
                exp_list.append({
                    "Expense_ID": str(r.get("Expense_ID", "")),
                    "Αφορά": target,
                    "Ημερομηνία": raw_date,
                    "Κατηγορία": cat,
                    "Ποσό": f"{amt:.2f} €".replace('.', ','),
                    "Λεπτομέρειες": details
                })
            
            if not exp_list:
                st.info("Δεν βρέθηκαν εγγραφές με τα επιλεγμένα κριτήρια.")
            else:
                html_code = f"""
                <!DOCTYPE html><html><head><style>{COMMON_CSS}</style></head><body>
                <div class="table-container">
                    <table id="exp-table" class="custom-table">
                        <thead>
                            <tr>
                                <th onclick="sortTable('exp-table', 0)">Αφορά (Ακίνητο/ΑΦΜ) ⇕</th>
                                <th onclick="sortTable('exp-table', 1)">Ημερομηνία ⇕</th>
                                <th onclick="sortTable('exp-table', 2)">Κατηγορία ⇕</th>
                                <th onclick="sortTable('exp-table', 3)">Ποσό ⇕</th>
                                <th onclick="sortTable('exp-table', 4)">Λεπτομέρειες ⇕</th>
                                <th>Ενέργεια</th>
                            </tr>
                        </thead>
                        <tbody>
                """
                for item in exp_list[::-1]:
                    html_code += f"""
                            <tr>
                                <td>{item['Αφορά']}</td>
                                <td>{item['Ημερομηνία']}</td>
                                <td>{item['Κατηγορία']}</td>
                                <td><strong>{item['Ποσό']}</strong></td>
                                <td>{item['Λεπτομέρειες']}</td>
                                <td><button class="action-btn" onclick="triggerPython('EDIT_{item['Expense_ID']}')">✏️ Επεξ.</button></td>
                            </tr>
                    """
                html_code += f"""
                        </tbody>
                    </table>
                </div>
                {COMMON_JS}
                </body></html>
                """
                t_height = min(600, 150 + len(exp_list) * 55)
                components.html(html_code, height=t_height, scrolling=False)

        st.write("")
        if st.button("➕ Προσθήκη Νέου Εξόδου", type="primary", use_container_width=True, key="btn_add_new_exp"):
            st.session_state.expense_action = 'new'
            st.rerun()
