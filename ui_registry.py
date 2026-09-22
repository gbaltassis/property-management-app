import streamlit as st
import gsheets_service
import pandas as pd
import uuid
import time
from datetime import date, datetime
import streamlit.components.v1 as components

MONTHS_DICT = {1:"Ιανουάριος", 2:"Φεβρουάριος", 3:"Μάρτιος", 4:"Απρίλιος", 5:"Μάιος", 6:"Ιούνιος", 
               7:"Ιούλιος", 8:"Αύγουστος", 9:"Σεπτέμβριος", 10:"Οκτώβριος", 11:"Νοέμβριος", 12:"Δεκέμβριος"}

COMMON_CSS = """
<style>
    html, body { font-family: sans-serif; }
    .table-container {
        height: 550px;
        overflow-y: auto;
        overflow-x: auto;
        border: 1px solid #ddd;
        border-radius: 8px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    .custom-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 13px; background: white; min-width: 900px; }
    .custom-table th, .custom-table td { padding: 10px; border-bottom: 1px solid #e6e9ef; border-right: 1px solid #e6e9ef; text-align: left; vertical-align: top; }
    .custom-table th { background-color: #f0f2f6; color: #31333F; position: sticky; top: 0; z-index: 4; box-shadow: 0 1px 0 #ddd; cursor: pointer; user-select: none; transition: background-color 0.2s;}
    .custom-table th:hover { background-color: #e2e6ea; }
    .custom-table th:first-child, .custom-table td:first-child { position: sticky; left: 0; z-index: 3; background-color: #ffffff; box-shadow: 1px 0 0 #ddd; font-weight: 600; min-width: 150px; }
    .custom-table th:first-child { z-index: 5; background-color: #f0f2f6; box-shadow: 1px 1px 0 #ddd; }
    
    .action-btn { display: block; width: 100%; background-color: #f8f9fa; border: 1px solid #ddd; padding: 6px 10px; border-radius: 4px; cursor: pointer; color: #31333F; font-size: 12px; font-weight: bold; transition: 0.2s; }
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
        .action-btn:hover { background-color: #2a2e37; color: #fff; }
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
                
                if(valX.match(/^\d{4}-\d{2}-\d{2}/)) valX = new Date(valX).getTime();
                if(valY.match(/^\d{4}-\d{2}-\d{2}/)) valY = new Date(valY).getTime();
                
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
                if (switchcount == 0 && dir == "asc") {
                    dir = "desc";
                    switching = true;
                }
            }
        }
    }

    (function hideInput() {
        var pDoc = window.parent.document;
        var inputs = pDoc.querySelectorAll('input[aria-label^="hidden_"]');
        if (inputs.length > 0) {
            inputs.forEach(function(input) {
                var wrapper = input.closest('div[data-testid="stTextInput"]');
                if (wrapper) { wrapper.style.position = 'absolute'; wrapper.style.opacity = '0'; wrapper.style.pointerEvents = 'none'; wrapper.style.height = '0px'; wrapper.style.overflow = 'hidden'; }
            });
        } else {
            setTimeout(hideInput, 100);
        }
    })();

    function triggerPython(action_val, input_name) {
        var payload = action_val + '|' + Date.now();
        var pDoc = window.parent.document;
        var input = pDoc.querySelector('input[aria-label="' + input_name + '"]');
        if(input) {
            var nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            nativeSetter.call(input, payload);
            input.dispatchEvent(new Event('input', {bubbles: true}));
            input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', keyCode: 13, which: 13, bubbles: true}));
        }
    }
</script>
"""

def handle_prop_action():
    val = st.session_state.hidden_prop_click_val
    if val:
        parts = val.split('|')
        if parts[0].startswith("EDIT_"):
            st.session_state.prop_action = 'edit'
            st.session_state.action_prop_id = parts[0].replace("EDIT_", "")
        st.session_state.hidden_prop_click_val = ""

def handle_tenant_action():
    val = st.session_state.hidden_tenant_click_val
    if val:
        parts = val.split('|')
        if parts[0].startswith("EDIT_"):
            st.session_state.tenant_action = 'edit'
            st.session_state.action_tenant_id = parts[0].replace("EDIT_", "")
        st.session_state.hidden_tenant_click_val = ""

def handle_ins_action():
    val = st.session_state.hidden_ins_click_val
    if val:
        parts = val.split('|')
        if parts[0].startswith("EDIT_"):
            st.session_state.ins_action = 'edit'
            st.session_state.action_ins_id = parts[0].replace("EDIT_", "")
        st.session_state.hidden_ins_click_val = ""

def show():
    # Setup States
    for key in ["prop_action", "action_prop_id", "tenant_action", "action_tenant_id", "ins_action", "action_ins_id"]:
        if key not in st.session_state: st.session_state[key] = None

    # Hidden inputs for routing
    st.text_input("hidden_prop_click", key="hidden_prop_click_val", label_visibility="collapsed", on_change=handle_prop_action)
    st.text_input("hidden_tenant_click", key="hidden_tenant_click_val", label_visibility="collapsed", on_change=handle_tenant_action)
    st.text_input("hidden_ins_click", key="hidden_ins_click_val", label_visibility="collapsed", on_change=handle_ins_action)

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

    main_tab_prop, main_tab_tenant, main_tab_ins = st.tabs(["🏢 Ακίνητα", "👥 Ενοικιαστές", "🛡️ Ασφαλιστήρια"])

    # =====================================================================
    # 1. ΑΚΙΝΗΤΑ
    # =====================================================================
    with main_tab_prop:
        if st.session_state.prop_action == 'new':
            st.markdown("### ➕ Νέο Ακίνητο")
            col_back, _ = st.columns([1, 4])
            if col_back.button("⬅️ Επιστροφή", key="back_prop_new", use_container_width=True):
                st.session_state.prop_action = None
                st.rerun()

            with st.form("new_property_form", clear_on_submit=True):
                charact, atak, dimos = st.text_input("Χαρακτηριστικό Ακινήτου *"), st.text_input("ΑΤΑΚ *"), st.text_input("Περιοχή / Δήμος *")
                nomos = st.text_input("Νομός", value="ΑΤΤΙΚΗΣ") 
                col1, col2 = st.columns(2)
                with col1: address = st.text_input("Οδός *")
                with col2: number = st.text_input("Αριθμός")
                col3, col4 = st.columns(2)
                with col3: floor = st.text_input("Όροφος")
                with col4: sqm_input = st.text_input("Επιφάνεια (m2) *", value="0")
                
                st.subheader("Οικονομικά Στοιχεία & Έξοδα")
                col5, col6 = st.columns(2)
                with col5: prop_val = st.text_input("Αντικειμενική Αξία Ακινήτου (€)", value="0")
                with col6: fixed_exp = st.text_input("Σταθερά Πάγια Έξοδα (Ετήσιο Budget σε €)", value="0")

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
                    
                if st.form_submit_button("Αποθήκευση Ακινήτου", type="primary", use_container_width=True):
                    sqm_val = pd.to_numeric(sqm_input.replace(',', '.'), errors='coerce')
                    if pd.isna(sqm_val): sqm_val = 0.0
                    if charact and atak and address and sqm_val > 0 and owner_data[0]:
                        try:
                            extra_str = ",".join(map(str, extra_months))
                            gsheets_service.add_property([f"PR-{uuid.uuid4().hex[:6].upper()}", atak, nomos, dimos, address, number, floor, sqm_input, charact] + owner_data + [extra_str, prop_val, "", fixed_exp])
                            st.success("Το ακίνητο αποθηκεύτηκε επιτυχώς!")
                            time.sleep(1.5)
                            st.session_state.prop_action = None
                            st.rerun()
                        except Exception as e: st.error(f"Σφάλμα: {e}")
                    else: st.warning("Συμπληρώστε τα υποχρεωτικά πεδία και τον 1ο Ιδιοκτήτη.")

        elif st.session_state.prop_action == 'edit':
            st.markdown("### ✏️ Επεξεργασία Ακινήτου")
            col_back, _ = st.columns([1, 4])
            if col_back.button("⬅️ Επιστροφή", key="back_prop_edit", use_container_width=True):
                st.session_state.prop_action = None
                st.rerun()

            sel_prop = properties_df[properties_df["Property_ID"] == st.session_state.action_prop_id].iloc[0]
            with st.form("edit_property_form"):
                e_charact, e_atak = st.text_input("Χαρακτηριστικό", value=str(sel_prop.get("Χαρακτηριστικό", ""))), st.text_input("ΑΤΑΚ", value=str(sel_prop.get("ΑΤΑΚ", "")))
                e_nomos, e_dimos = st.text_input("Νομός", value=str(sel_prop.get("Νομός", ""))), st.text_input("Περιοχή / Δήμος", value=str(sel_prop.get("Περιοχή/Δήμος", "")))
                ec1, ec2 = st.columns(2)
                with ec1: e_address = st.text_input("Οδός", value=str(sel_prop.get("Διεύθυνση", "")))
                with ec2: e_number = st.text_input("Αριθμός", value=str(sel_prop.get("Αριθμός", "")))
                ec3, ec4 = st.columns(2)
                with ec3: e_floor = st.text_input("Όροφος", value=str(sel_prop.get("Όροφος", "")))
                with ec4: e_sqm = st.text_input("Επιφάνεια (m2)", value=str(sel_prop.get("Επιφάνεια m2", "")))
                
                st.subheader("Οικονομικά Στοιχεία & Έξοδα")
                col5, col6 = st.columns(2)
                with col5: e_prop_val = st.text_input("Αντικειμενική Αξία Ακινήτου (€)", value=str(sel_prop.get("Property_Value", "")).replace('.', ','))
                with col6: e_fixed_exp = st.text_input("Σταθερά Πάγια Έξοδα (Ετήσιο Budget σε €)", value=str(sel_prop.get("Fixed_Yearly_Expenses", "")).replace('.', ','))

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
                        
                update_btn = st.form_submit_button("Αποθήκευση Αλλαγών", type="primary", use_container_width=True)
                
            if st.button("🗑️ Οριστική Διαγραφή Ακινήτου", use_container_width=True):
                try:
                    gsheets_service.delete_property(st.session_state.action_prop_id)
                    st.success("Το ακίνητο διαγράφηκε!")
                    time.sleep(1.5)
                    st.session_state.prop_action = None
                    st.rerun()
                except Exception as e: st.error(f"Σφάλμα: {e}")

            if update_btn:
                try:
                    e_extra_str = ",".join(map(str, e_extra_months))
                    gsheets_service.update_property(st.session_state.action_prop_id, [st.session_state.action_prop_id, e_atak, e_nomos, e_dimos, e_address, e_number, e_floor, e_sqm, e_charact] + e_owner_data + [e_extra_str, e_prop_val, "", e_fixed_exp])
                    st.success("Αποθηκεύτηκαν!")
                    time.sleep(1.5)
                    st.session_state.prop_action = None
                    st.rerun()
                except Exception as e: st.error(f"Σφάλμα: {e}")

        else:
            if properties_df.empty: 
                st.info("Δεν υπάρχουν καταχωρημένα ακίνητα.")
            else:
                html_code = f"""
                <!DOCTYPE html><html><head><style>{COMMON_CSS}</style></head><body>
                <div class="table-container">
                    <table id="prop-table" class="custom-table">
                        <thead>
                            <tr>
                                <th onclick="sortTable('prop-table', 0)">Χαρακτηριστικό ⇕</th>
                                <th onclick="sortTable('prop-table', 1)">Διεύθυνση ⇕</th>
                                <th onclick="sortTable('prop-table', 2)">Μήνες Λογαριασμών ⇕</th>
                                <th onclick="sortTable('prop-table', 3)">Ιδιοκτησιακό Καθεστώς ⇕</th>
                                <th>Ενέργεια</th>
                            </tr>
                        </thead>
                        <tbody>
                """
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
                    
                    p_id = str(prop.get("Property_ID", ""))
                    html_code += f"""
                            <tr>
                                <td>{prop.get("Χαρακτηριστικό", "-")}</td>
                                <td>{prop.get("Διεύθυνση", "")} {prop.get("Αριθμός", "")}</td>
                                <td>{e_months_text if e_months_text else "-"}</td>
                                <td>{" | ".join(owners_list) if owners_list else "Μη ορισμένο"}</td>
                                <td><button class="action-btn" onclick="triggerPython('EDIT_{p_id}', 'hidden_prop_click')">✏️ Επεξ.</button></td>
                            </tr>
                    """
                html_code += f"""
                        </tbody>
                    </table>
                </div>
                {COMMON_JS}
                </body></html>
                """
                components.html(html_code, height=580, scrolling=False)
                
            if st.button("➕ Νέο Ακίνητο", type="primary", use_container_width=True):
                st.session_state.prop_action = 'new'
                st.rerun()

    # =====================================================================
    # 2. ΕΝΟΙΚΙΑΣΤΕΣ
    # =====================================================================
    with main_tab_tenant:
        if st.session_state.tenant_action == 'new':
            st.markdown("### ➕ Νέος Ενοικιαστής")
            col_back, _ = st.columns([1, 4])
            if col_back.button("⬅️ Επιστροφή", key="back_tenant_new", use_container_width=True):
                st.session_state.tenant_action = None
                st.rerun()

            with st.form("new_tenant_form", clear_on_submit=True):
                fname, lname, afm = st.text_input("Όνομα *"), st.text_input("Επώνυμο *"), st.text_input("ΑΦΜ *")
                phone, email = st.text_input("Κινητό Τηλέφωνο"), st.text_input("Email")
                if st.form_submit_button("Αποθήκευση Ενοικιαστή", type="primary", use_container_width=True):
                    if fname and lname and afm:
                        try:
                            gsheets_service.add_tenant([f"TN-{uuid.uuid4().hex[:6].upper()}", fname, lname, afm, phone, email])
                            st.success("Ο ενοικιαστής αποθηκεύτηκε!")
                            time.sleep(1.5)
                            st.session_state.tenant_action = None
                            st.rerun()
                        except Exception as e: st.error(f"Σφάλμα: {e}")
                    else: st.warning("Παρακαλώ συμπληρώστε Όνομα, Επώνυμο, ΑΦΜ.")

        elif st.session_state.tenant_action == 'edit':
            st.markdown("### ✏️ Επεξεργασία Ενοικιαστή")
            col_back, _ = st.columns([1, 4])
            if col_back.button("⬅️ Επιστροφή", key="back_tenant_edit", use_container_width=True):
                st.session_state.tenant_action = None
                st.rerun()

            sel_ten = tenants_df[tenants_df["Tenant_ID"] == st.session_state.action_tenant_id].iloc[0]
            with st.form("edit_tenant_form"):
                e_t_fname, e_t_lname = st.text_input("Όνομα *", value=str(sel_ten.get("Όνομα", ""))), st.text_input("Επώνυμο *", value=str(sel_ten.get("Επώνυμο", "")))
                afm_v = str(sel_ten.get("ΑΦΜ", ""))
                if len(afm_v) == 8: afm_v = "0" + afm_v
                e_t_afm = st.text_input("ΑΦΜ *", value=afm_v)
                e_t_phone, e_t_email = st.text_input("Κινητό Τηλέφωνο", value=str(sel_ten.get("Κινητό", ""))), st.text_input("Email", value=str(sel_ten.get("Email", "")))
                upd_t_btn = st.form_submit_button("Αποθήκευση Αλλαγών", type="primary", use_container_width=True)
                
            if st.button("🗑️ Οριστική Διαγραφή Ενοικιαστή", use_container_width=True):
                try:
                    gsheets_service.delete_tenant(st.session_state.action_tenant_id)
                    st.success("Ο ενοικιαστής διαγράφηκε!")
                    time.sleep(1.5)
                    st.session_state.tenant_action = None
                    st.rerun()
                except Exception as e: st.error(f"Σφάλμα: {e}")

            if upd_t_btn:
                if e_t_fname and e_t_lname and e_t_afm:
                    try:
                        gsheets_service.update_tenant(st.session_state.action_tenant_id, [st.session_state.action_tenant_id, e_t_fname, e_t_lname, e_t_afm, e_t_phone, e_t_email])
                        st.success("Αποθηκεύτηκαν!")
                        time.sleep(1.5)
                        st.session_state.tenant_action = None
                        st.rerun()
                    except Exception as e: st.error(f"Σφάλμα: {e}")
                else: st.warning("Παρακαλώ συμπληρώστε Όνομα, Επώνυμο, ΑΦΜ.")

        else:
            if tenants_df.empty: 
                st.info("Δεν υπάρχουν καταχωρημένοι ενοικιαστές.")
            else:
                html_code = f"""
                <!DOCTYPE html><html><head><style>{COMMON_CSS}</style></head><body>
                <div class="table-container">
                    <table id="tenant-table" class="custom-table">
                        <thead>
                            <tr>
                                <th onclick="sortTable('tenant-table', 0)">Ονοματεπώνυμο ⇕</th>
                                <th onclick="sortTable('tenant-table', 1)">ΑΦΜ ⇕</th>
                                <th onclick="sortTable('tenant-table', 2)">Επικοινωνία ⇕</th>
                                <th onclick="sortTable('tenant-table', 3)">Συνδεδεμένο Ακίνητο ⇕</th>
                                <th>Ενέργεια</th>
                            </tr>
                        </thead>
                        <tbody>
                """
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
                        
                        html_code += f"""
                            <tr>
                                <td>{str(tenant.get('Επώνυμο', ''))} {str(tenant.get('Όνομα', ''))}</td>
                                <td>{str(tenant.get("ΑΦΜ", ""))}</td>
                                <td>{str(tenant.get('Κινητό', ''))} | {str(tenant.get('Email', ''))}</td>
                                <td>{linked_prop_charact}</td>
                                <td><button class="action-btn" onclick="triggerPython('EDIT_{t_id}', 'hidden_tenant_click')">✏️ Επεξ.</button></td>
                            </tr>
                        """
                html_code += f"""
                        </tbody>
                    </table>
                </div>
                {COMMON_JS}
                </body></html>
                """
                components.html(html_code, height=580, scrolling=False)

            if st.button("➕ Νέος Ενοικιαστής", type="primary", use_container_width=True):
                st.session_state.tenant_action = 'new'
                st.rerun()

    # =====================================================================
    # 3. ΑΣΦΑΛΙΣΤΗΡΙΑ
    # =====================================================================
    with main_tab_ins:
        if st.session_state.ins_action == 'new':
            st.markdown("### ➕ Νέο Ασφαλιστήριο")
            col_back, _ = st.columns([1, 4])
            if col_back.button("⬅️ Επιστροφή", key="back_ins_new", use_container_width=True):
                st.session_state.ins_action = None
                st.rerun()

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
                    
                    if st.form_submit_button("Αποθήκευση Ασφαλιστηρίου", type="primary", use_container_width=True):
                        if i_comp and i_num:
                            try:
                                ins_id = f"INS-{uuid.uuid4().hex[:6].upper()}"
                                gsheets_service.add_insurance([ins_id, i_prop, i_cat, i_comp, i_num, i_date.strftime("%Y-%m-%d"), i_dur, i_prem, i_build, i_cont])
                                st.success("Το ασφαλιστήριο καταχωρήθηκε επιτυχώς!")
                                time.sleep(1.5)
                                st.session_state.ins_action = None
                                st.rerun()
                            except Exception as e: st.error(f"Σφάλμα: {e}")
                        else: st.warning("Συμπληρώστε υποχρεωτικά την Εταιρεία και τον Αριθμό Συμβολαίου.")

        elif st.session_state.ins_action == 'edit':
            st.markdown("### ✏️ Επεξεργασία Ασφαλιστηρίου")
            col_back, _ = st.columns([1, 4])
            if col_back.button("⬅️ Επιστροφή", key="back_ins_edit", use_container_width=True):
                st.session_state.ins_action = None
                st.rerun()

            sel_ins = insurances_df[insurances_df["Insurance_ID"] == st.session_state.action_ins_id].iloc[0]
            prop_options = {row["Property_ID"]: f"{row.get('Χαρακτηριστικό', '')} ({row.get('Διεύθυνση', '')})" for _, row in properties_df.iterrows()}
            
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
                    gsheets_service.delete_insurance(st.session_state.action_ins_id)
                    st.success("Το ασφαλιστήριο διαγράφηκε!")
                    time.sleep(1.5)
                    st.session_state.ins_action = None
                    st.rerun()
                except Exception as e: st.error(f"Σφάλμα: {e}")

            if upd_i_btn:
                if e_comp and e_num:
                    try:
                        new_row = [st.session_state.action_ins_id, e_prop, e_cat, e_comp, e_num, e_date.strftime("%Y-%m-%d"), e_dur, e_prem, e_build, e_cont]
                        gsheets_service.update_insurance(st.session_state.action_ins_id, new_row)
                        st.success("Οι αλλαγές αποθηκεύτηκαν!")
                        time.sleep(1.5)
                        st.session_state.ins_action = None
                        st.rerun()
                    except Exception as e: st.error(f"Σφάλμα επεξεργασίας: {e}")
                else: st.warning("Συμπληρώστε υποχρεωτικά την Εταιρεία και τον Αριθμό Συμβολαίου.")

        else:
            if insurances_df.empty: 
                st.info("Δεν υπάρχουν καταχωρημένα ασφαλιστήρια συμβόλαια.")
            else:
                html_code = f"""
                <!DOCTYPE html><html><head><style>{COMMON_CSS}</style></head><body>
                <div class="table-container">
                    <table id="ins-table" class="custom-table">
                        <thead>
                            <tr>
                                <th onclick="sortTable('ins-table', 0)">Ακίνητο ⇕</th>
                                <th onclick="sortTable('ins-table', 1)">Κατηγορία ⇕</th>
                                <th onclick="sortTable('ins-table', 2)">Εταιρεία (Αρ. Συμβολαίου) ⇕</th>
                                <th onclick="sortTable('ins-table', 3)">Λήξη / Ανανέωση ⇕</th>
                                <th onclick="sortTable('ins-table', 4)">Ασφάλιστρο ⇕</th>
                                <th>Ενέργεια</th>
                            </tr>
                        </thead>
                        <tbody>
                """
                for _, ins in insurances_df.iterrows():
                    i_id = str(ins.get("Insurance_ID", ""))
                    p_id = str(ins.get("Property_ID", ""))
                    p_charact = "-"
                    if not properties_df.empty:
                        p_match = properties_df[properties_df["Property_ID"] == p_id]
                        if not p_match.empty: p_charact = str(p_match.iloc[0].get("Χαρακτηριστικό", "-"))
                    
                    prem = pd.to_numeric(str(ins.get('Premium', '0')).replace(',', '.'), errors='coerce')
                    prem_txt = f"{prem:.2f} €".replace('.', ',') if pd.notna(prem) and prem > 0 else "-"
                    
                    html_code += f"""
                            <tr>
                                <td>{p_charact}</td>
                                <td>{str(ins.get("Category", ""))}</td>
                                <td>{ins.get('Company', '')} ({ins.get('Contract_Number', '')})</td>
                                <td>{str(ins.get("Renewal_Date", ""))}</td>
                                <td><strong>{prem_txt}</strong></td>
                                <td><button class="action-btn" onclick="triggerPython('EDIT_{i_id}', 'hidden_ins_click')">✏️ Επεξ.</button></td>
                            </tr>
                    """
                html_code += f"""
                        </tbody>
                    </table>
                </div>
                {COMMON_JS}
                </body></html>
                """
                components.html(html_code, height=580, scrolling=False)

            if st.button("➕ Νέο Ασφαλιστήριο", type="primary", use_container_width=True):
                st.session_state.ins_action = 'new'
                st.rerun()
