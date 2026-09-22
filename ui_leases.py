import streamlit as st
import gsheets_service
import uuid
import pandas as pd
import time
from datetime import date, datetime
import streamlit.components.v1 as components

COMMON_CSS = """
<style>
    html, body { font-family: sans-serif; background-color: transparent; }
    .table-container { 
        max-height: 550px; overflow-y: auto; overflow-x: auto; 
        border: 1px solid #ddd; border-radius: 8px; 
        box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 20px; 
    }
    .custom-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 12px; background: white; min-width: 800px; }
    .custom-table th, .custom-table td { padding: 6px 8px; border-bottom: 1px solid #e6e9ef; border-right: 1px solid #e6e9ef; text-align: left; vertical-align: middle; line-height: 1.2; }
    .custom-table th { background-color: #f0f2f6; color: #31333F; position: sticky; top: 0; z-index: 4; box-shadow: 0 1px 0 #ddd; cursor: pointer; user-select: none; transition: background-color 0.2s;}
    .custom-table th:hover { background-color: #e2e6ea; }
    .custom-table th:first-child, .custom-table td:first-child { 
        position: sticky; left: 0; z-index: 3; background-color: #ffffff; 
        box-shadow: 1px 0 0 #ddd; font-weight: 600; 
        min-width: 80px; max-width: 120px; 
        white-space: normal !important; word-wrap: break-word; 
    }
    .custom-table th:first-child { z-index: 5; background-color: #f0f2f6; box-shadow: 1px 1px 0 #ddd; }
    
    .action-btn { display: block; width: 100%; background-color: #f8f9fa; border: 1px solid #ddd; padding: 4px; border-radius: 4px; cursor: pointer; color: #31333F; font-size: 11px; font-weight: bold; transition: 0.2s; text-align: center; }
    .action-btn:hover { background-color: #e2e6ea; border-color: #dae0e5; }
    .status-badge { padding: 3px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; display: inline-block; }
    .status-active { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
    .status-expired { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }

    @media (prefers-color-scheme: dark) {
        .table-container { border-color: #444; }
        .custom-table { background: #0e1117; color: white; }
        .custom-table th { background-color: #262730; color: white; box-shadow: 0 1px 0 #444; }
        .custom-table th:hover { background-color: #383a45; }
        .custom-table th:first-child, .custom-table td:first-child { background-color: #0e1117; box-shadow: 1px 0 0 #666; color: white; }
        .custom-table th:first-child { background-color: #262730; box-shadow: 1px 1px 0 #666; }
        .custom-table td { border-color: #444; color: white; }
        .action-btn { background-color: #1e2127; border-color: #444; color: #ddd; }
        .action-btn:hover { background-color: #2a2e37; color: #fff; }
        .status-active { background-color: #155724; color: #d4edda; border-color: #155724; }
        .status-expired { background-color: #721c24; color: #f8d7da; border-color: #721c24; }
    }
</style>
"""

COMMON_JS = """
<script>
    function sortTable(tableId, n) {
        var table, rows, switching, i, x, y, shouldSwitch, dir, switchcount = 0;
        table = document.getElementById(tableId);
        switching = true; dir = "asc"; 
        while (switching) {
            switching = false; rows = table.getElementsByTagName("TR");
            for (i = 1; i < (rows.length - 1); i++) {
                shouldSwitch = false;
                x = rows[i].getElementsByTagName("TD")[n]; y = rows[i + 1].getElementsByTagName("TD")[n];
                if(!x || !y) continue;
                let valX = x.innerText.trim().toLowerCase(); let valY = y.innerText.trim().toLowerCase();
                if(valX.includes('€')) valX = parseFloat(valX.replace(/[^0-9,-]/g, '').replace(',', '.'));
                if(valY.includes('€')) valY = parseFloat(valY.replace(/[^0-9,-]/g, '').replace(',', '.'));
                if(valX.match(/^\\d{4}-\\d{2}-\\d{2}/)) valX = new Date(valX).getTime();
                if(valY.match(/^\\d{4}-\\d{2}-\\d{2}/)) valY = new Date(valY).getTime();
                if (dir == "asc") { if (valX > valY) { shouldSwitch = true; break; } } 
                else if (dir == "desc") { if (valX < valY) { shouldSwitch = true; break; } }
            }
            if (shouldSwitch) { rows[i].parentNode.insertBefore(rows[i + 1], rows[i]); switching = true; switchcount ++; } 
            else { if (switchcount == 0 && dir == "asc") { dir = "desc"; switching = true; } }
        }
    }
    (function hideInput() {
        var pDoc = window.parent.document;
        var inputs = pDoc.querySelectorAll('input[aria-label="hidden_lease_click"]');
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
        var input = pDoc.querySelector('input[aria-label="hidden_lease_click"]');
        if(input) {
            var nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            nativeSetter.call(input, payload);
            input.dispatchEvent(new Event('input', {bubbles: true}));
            input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', keyCode: 13, which: 13, bubbles: true}));
        }
    }
</script>
"""

def handle_lease_action():
    key_name = st.session_state.current_lease_hidden_key
    val = st.session_state.get(key_name, "")
    if val:
        parts = val.split('|')
        action = parts[0]
        if action.startswith("EDIT_"):
            st.session_state.lease_action = 'edit'
            st.session_state.action_lease_id = action.replace("EDIT_", "")
        st.session_state[key_name] = ""

def show():
    if "lease_action" not in st.session_state:
        st.session_state.lease_action = None
    if "action_lease_id" not in st.session_state:
        st.session_state.action_lease_id = None

    if "current_lease_hidden_key" not in st.session_state:
        st.session_state.current_lease_hidden_key = f"hidden_lease_click_val_{uuid.uuid4().hex[:8]}"

    st.text_input("hidden_lease_click", key=st.session_state.current_lease_hidden_key, label_visibility="collapsed", on_change=handle_lease_action)
    st.markdown(COMMON_CSS, unsafe_allow_html=True)
    
    try:
        properties_df = gsheets_service.fetch_all_properties()
        tenants_df = gsheets_service.fetch_all_tenants()
        leases_df = gsheets_service.fetch_all_leases()
    except Exception as e:
        st.error(f"Αδυναμία φόρτωσης δεδομένων: {e}")
        return

    prop_options = {}
    if not properties_df.empty:
        for _, p in properties_df.iterrows():
            prop_options[str(p.get("Property_ID", ""))] = f"{str(p.get('Χαρακτηριστικό', ''))} ({str(p.get('Διεύθυνση', ''))})"
            
    tenant_options = {}
    if not tenants_df.empty:
        for _, t in tenants_df.iterrows():
            tenant_options[str(t.get("Tenant_ID", ""))] = f"{str(t.get('Επώνυμο', ''))} {str(t.get('Όνομα', ''))} (ΑΦΜ: {str(t.get('ΑΦΜ', ''))})"

    st.header("Διαχείριση Μισθώσεων")

    if st.session_state.lease_action == 'new':
        st.markdown("### ➕ Προσθήκη Νέας Μίσθωσης")
        col_back, _ = st.columns([1, 4])
        if col_back.button("⬅️ Επιστροφή", use_container_width=True, key="back_btn_lease_new"):
            st.session_state.lease_action = None
            st.rerun()

        if properties_df.empty or tenants_df.empty:
            st.warning("Πρέπει να καταχωρήσετε τουλάχιστον 1 Ακίνητο και 1 Ενοικιαστή στο Μητρώο.")
        else:
            with st.form("new_lease_form", clear_on_submit=True):
                l_prop = st.selectbox("Ακίνητο *", list(prop_options.keys()), format_func=lambda x: prop_options[x], key="new_lease_prop")
                l_tenants = st.multiselect("Ενοικιαστής/ές *", list(tenant_options.keys()), format_func=lambda x: tenant_options[x], key="new_lease_tenants")
                
                c1, c2 = st.columns(2)
                with c1: start_d = st.date_input("Έναρξη *", value=date.today(), key="new_lease_start")
                with c2: end_d = st.date_input("Λήξη *", value=date(date.today().year + 3, date.today().month, date.today().day), key="new_lease_end")
                
                c3, c4 = st.columns(2)
                with c3: rent = st.text_input("Μηνιαίο Μίσθωμα (€) *", value="0", key="new_lease_rent")
                with c4: guar = st.text_input("Εγγύηση (€)", value="0", key="new_lease_guar")
                
                adj = st.text_input("Όροι Αναπροσαρμογής (π.χ. +5% το 2ο έτος)", key="new_lease_adj")
                
                if st.form_submit_button("Αποθήκευση Μίσθωσης", type="primary", use_container_width=True):
                    rent_val = pd.to_numeric(rent.replace(',', '.'), errors='coerce')
                    if not l_tenants:
                        st.warning("Επιλέξτε τουλάχιστον 1 Ενοικιαστή.")
                    elif pd.isna(rent_val) or rent_val <= 0:
                        st.warning("Παρακαλώ εισάγετε έγκυρο Μίσθωμα.")
                    else:
                        lease_id = f"LS-{uuid.uuid4().hex[:6].upper()}"
                        tenants_str = ",".join(l_tenants)
                        row = [lease_id, l_prop, tenants_str, start_d.strftime("%Y-%m-%d"), end_d.strftime("%Y-%m-%d"), str(rent).replace('.', ','), str(guar).replace('.', ','), adj]
                        try:
                            gsheets_service.add_lease(row)
                            st.success("Η μίσθωση καταχωρήθηκε επιτυχώς!")
                            time.sleep(1.5)
                            st.session_state.lease_action = None
                            st.rerun()
                        except Exception as e: st.error(f"Σφάλμα: {e}")

    elif st.session_state.lease_action == 'edit':
        st.markdown("### ✏️ Επεξεργασία Μίσθωσης")
        col_back, _ = st.columns([1, 4])
        if col_back.button("⬅️ Επιστροφή", use_container_width=True, key="back_btn_lease_edit"):
            st.session_state.lease_action = None
            st.rerun()

        sel_id = st.session_state.action_lease_id
        sel_row = leases_df[leases_df["Lease_ID"] == sel_id].iloc[0]
        
        with st.form("edit_lease_form"):
            curr_prop = str(sel_row.get("Property_ID", ""))
            p_keys = list(prop_options.keys())
            try: p_idx = p_keys.index(curr_prop)
            except: p_idx = 0
            e_prop = st.selectbox("Ακίνητο *", p_keys, index=p_idx, format_func=lambda x: prop_options[x], key=f"e_lease_prop_{sel_id}")
            
            curr_tenants_raw = str(sel_row.get("Tenant_ID", "")).split(',')
            curr_tenants = [t.strip() for t in curr_tenants_raw if t.strip() in tenant_options]
            e_tenants = st.multiselect("Ενοικιαστής/ές *", list(tenant_options.keys()), default=curr_tenants, format_func=lambda x: tenant_options[x], key=f"e_lease_tenants_{sel_id}")
            
            try: st_d = datetime.strptime(str(sel_row.get("Start_Date", "")), "%Y-%m-%d").date()
            except: st_d = date.today()
            try: en_d = datetime.strptime(str(sel_row.get("End_Date", "")), "%Y-%m-%d").date()
            except: en_d = date(date.today().year + 3, date.today().month, date.today().day)
            
            c1, c2 = st.columns(2)
            with c1: e_start = st.date_input("Έναρξη *", value=st_d, key=f"e_lease_st_{sel_id}")
            with c2: e_end = st.date_input("Λήξη *", value=en_d, key=f"e_lease_en_{sel_id}")
            
            c3, c4 = st.columns(2)
            with c3: e_rent = st.text_input("Μηνιαίο Μίσθωμα (€) *", value=str(sel_row.get("Monthly_Rent", "")).replace('.', ','), key=f"e_lease_rent_{sel_id}")
            with c4: e_guar = st.text_input("Εγγύηση (€)", value=str(sel_row.get("Guarantee", "")).replace('.', ','), key=f"e_lease_guar_{sel_id}")
            
            e_adj = st.text_input("Όροι Αναπροσαρμογής", value=str(sel_row.get("Adjustment_Terms", "")).replace('nan',''), key=f"e_lease_adj_{sel_id}")
            
            upd_btn = st.form_submit_button("Αποθήκευση Αλλαγών", type="primary", use_container_width=True)
            
        if st.button("🗑️ Οριστική Διαγραφή Μίσθωσης", use_container_width=True, key=f"del_lease_{sel_id}"):
            try:
                gsheets_service.delete_lease(sel_id)
                st.success("Διαγράφηκε! Η σελίδα ανανεώνεται...")
                time.sleep(1.5)
                st.session_state.lease_action = None
                st.rerun()
            except Exception as e: st.error(f"Σφάλμα: {e}")

        if upd_btn:
            rent_val = pd.to_numeric(e_rent.replace(',', '.'), errors='coerce')
            if not e_tenants:
                st.warning("Επιλέξτε τουλάχιστον 1 Ενοικιαστή.")
            elif pd.isna(rent_val) or rent_val <= 0:
                st.warning("Παρακαλώ εισάγετε έγκυρο Μίσθωμα.")
            else:
                tenants_str = ",".join(e_tenants)
                new_row = [sel_id, e_prop, tenants_str, e_start.strftime("%Y-%m-%d"), e_end.strftime("%Y-%m-%d"), str(e_rent).replace('.', ','), str(e_guar).replace('.', ','), e_adj]
                try:
                    gsheets_service.update_lease(sel_id, new_row)
                    st.success("Οι αλλαγές αποθηκεύτηκαν!")
                    time.sleep(1.5)
                    st.session_state.lease_action = None
                    st.rerun()
                except Exception as e: st.error(f"Σφάλμα επεξεργασίας: {e}")

    else:
        st.caption("Ιστορικό Όλων των Μισθώσεων")
        if leases_df.empty: 
            st.info("Δεν υπάρχουν καταχωρημένες μισθώσεις.")
        else:
            fc1, fc2, fc3 = st.columns(3)
            
            all_years = set()
            for _, r in leases_df.iterrows():
                try: 
                    sy = datetime.strptime(str(r.get("Start_Date", "")), "%Y-%m-%d").date().year
                    ey = datetime.strptime(str(r.get("End_Date", "")), "%Y-%m-%d").date().year
                    for y in range(sy, ey + 1): all_years.add(str(y))
                except: pass
            sorted_years = ["Όλα τα έτη"] + sorted(list(all_years), reverse=True)
            sel_year = fc1.selectbox("Επιλογή Έτους (Ενεργή)", sorted_years, key="filter_lease_year")

            all_props = ["Όλα τα ακίνητα"] + [prop_options[k] for k in prop_options.keys()]
            sel_prop = fc2.selectbox("Ακίνητο", all_props, key="filter_lease_prop")
            
            sel_status = fc3.selectbox("Κατάσταση", ["Όλες", "Ενεργές", "Ληγμένες"], key="filter_lease_status")

            st.write("") 

            lease_list = []
            today = date.today()
            
            for _, r in leases_df.iterrows():
                p_id = str(r.get("Property_ID", ""))
                p_name = prop_options.get(p_id, "-")
                
                if sel_prop != "Όλα τα ακίνητα" and p_name != sel_prop: continue
                
                t_names = []
                for tid_clean in [t.strip() for t in str(r.get("Tenant_ID", "")).split(',') if t.strip()]:
                    if tid_clean in tenant_options: t_names.append(tenant_options[tid_clean].split(" (")[0])
                t_display = " & ".join(t_names) if t_names else "Άγνωστος"
                
                s_date_str = str(r.get("Start_Date", ""))
                e_date_str = str(r.get("End_Date", ""))
                try: s_d = datetime.strptime(s_date_str, "%Y-%m-%d").date()
                except: s_d = date(1900, 1, 1)
                try: e_d = datetime.strptime(e_date_str, "%Y-%m-%d").date()
                except: e_d = date(2099, 12, 31)
                
                if sel_year != "Όλα τα έτη":
                    y_int = int(sel_year)
                    if not (s_d.year <= y_int <= e_d.year): continue
                
                is_active = e_d >= today
                if sel_status == "Ενεργές" and not is_active: continue
                if sel_status == "Ληγμένες" and is_active: continue
                
                status_html = "<span class='status-badge status-active'>Ενεργή</span>" if is_active else "<span class='status-badge status-expired'>Ληγμένη</span>"

                rent = pd.to_numeric(str(r.get('Monthly_Rent', '0')).replace(',', '.'), errors='coerce')
                rent_disp = f"{rent:.2f} €".replace('.', ',') if pd.notna(rent) else "0,00 €"
                
                lease_list.append({
                    "Lease_ID": str(r.get("Lease_ID", "")),
                    "Ακίνητο": p_name,
                    "Ενοικιαστής": t_display,
                    "Έναρξη": s_date_str,
                    "Λήξη": e_date_str,
                    "Μίσθωμα": rent_disp,
                    "Κατάσταση": status_html
                })
            
            if not lease_list:
                st.info("Δεν βρέθηκαν μισθώσεις με τα επιλεγμένα κριτήρια.")
            else:
                html_code = f"""
                <!DOCTYPE html><html><head><style>{COMMON_CSS}</style></head><body>
                <div class="table-container">
                    <table id="lease-table" class="custom-table">
                        <thead>
                            <tr>
                                <th onclick="sortTable('lease-table', 0)">Ακίνητο ⇕</th>
                                <th onclick="sortTable('lease-table', 1)">Ενοικιαστής/ές ⇕</th>
                                <th onclick="sortTable('lease-table', 2)">Έναρξη ⇕</th>
                                <th onclick="sortTable('lease-table', 3)">Λήξη ⇕</th>
                                <th onclick="sortTable('lease-table', 4)">Μίσθωμα ⇕</th>
                                <th onclick="sortTable('lease-table', 5)">Κατάσταση ⇕</th>
                                <th>Ενέργεια</th>
                            </tr>
                        </thead>
                        <tbody>
                """
                for item in lease_list:
                    html_code += f"""
                            <tr>
                                <td>{item['Ακίνητο']}</td>
                                <td>{item['Ενοικιαστής']}</td>
                                <td>{item['Έναρξη']}</td>
                                <td>{item['Λήξη']}</td>
                                <td><strong>{item['Μίσθωμα']}</strong></td>
                                <td>{item['Κατάσταση']}</td>
                                <td><button class="action-btn" onclick="triggerPython('EDIT_{item['Lease_ID']}')">✏️ Επεξ.</button></td>
                            </tr>
                    """
                html_code += f"""
                        </tbody>
                    </table>
                </div>
                {COMMON_JS}
                </body></html>
                """
                t_height = min(600, 70 + len(lease_list) * 55)
                components.html(html_code, height=t_height, scrolling=False)

        st.write("")
        if st.button("➕ Προσθήκη Νέας Μίσθωσης", type="primary", use_container_width=True, key="btn_add_new_lease"):
            st.session_state.lease_action = 'new'
            st.rerun()
