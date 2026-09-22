import streamlit as st
import gsheets_service
import uuid
import pandas as pd
import time
from datetime import date, datetime
import streamlit.components.v1 as components

COMMON_CSS = """
<style>
    html, body { font-family: sans-serif; }
    .matrix-wrapper { height: 100%; width: 100%; overflow: auto; border: 1px solid #ddd; border-radius: 8px; box-sizing: border-box; }
    .matrix-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 13px; background: white; min-width: 950px; }
    .matrix-table th, .matrix-table td { padding: 6px; text-align: center; border-bottom: 1px solid #ddd; border-right: 1px solid #ddd; }
    .matrix-table th { background-color: #f0f2f6; color: #31333F; position: sticky; top: 0; z-index: 4; box-shadow: 0 1px 0 #ddd; padding: 10px 6px; }
    .matrix-table th:first-child, .matrix-table td:first-child { position: sticky; left: 0; background-color: #ffffff; z-index: 5; text-align: left; min-width: 140px; max-width: 180px; white-space: normal !important; word-wrap: break-word; box-shadow: 1px 0 0 #bbb; }
    .matrix-table th:first-child { z-index: 6; box-shadow: 1px 1px 0 #bbb; }
    .matrix-cell-btn { display: block; width: 100%; text-align: center; color: #31333F; padding: 6px; border-radius: 4px; background-color: #f8f9fa; border: 1px solid #e9ecef; margin-bottom: 4px; font-weight: 500; cursor: pointer; transition: all 0.2s; font-size: 12px; line-height: 1.3; }
    .matrix-cell-btn:hover { background-color: #e2e6ea; border-color: #dae0e5; color: #000; }
    .matrix-cell-empty { display: block; width: 100%; text-align: center; color: #6c757d; padding: 6px; cursor: pointer; background: none; border: none; font-size: 12px; }

    .table-container { height: 550px; overflow-y: auto; overflow-x: auto; border: 1px solid #ddd; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 20px; }
    .custom-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 13px; background: white; min-width: 950px; }
    .custom-table th, .custom-table td { padding: 10px; border-bottom: 1px solid #e6e9ef; border-right: 1px solid #e6e9ef; text-align: left; vertical-align: middle; }
    .custom-table th { background-color: #f0f2f6; color: #31333F; position: sticky; top: 0; z-index: 4; box-shadow: 0 1px 0 #ddd; cursor: pointer; user-select: none; transition: background-color 0.2s; }
    .custom-table th:hover { background-color: #e2e6ea; }
    .custom-table th:first-child, .custom-table td:first-child { position: sticky; left: 0; z-index: 3; background-color: #ffffff; box-shadow: 1px 0 0 #ddd; font-weight: 600; min-width: 120px; max-width: 160px; white-space: normal !important; word-wrap: break-word; }
    .custom-table th:first-child { z-index: 5; background-color: #f0f2f6; box-shadow: 1px 1px 0 #ddd; }
    .action-btn { display: block; width: 100%; background-color: #f8f9fa; border: 1px solid #ddd; padding: 6px 10px; border-radius: 4px; cursor: pointer; color: #31333F; font-size: 12px; font-weight: bold; transition: 0.2s; text-align: center; }
    .action-btn:hover { background-color: #e2e6ea; border-color: #dae0e5; }

    @media (prefers-color-scheme: dark) {
        .matrix-wrapper, .table-container { border-color: #444; }
        .matrix-table, .custom-table { background: #0e1117; color: white; }
        .matrix-table th, .custom-table th { background-color: #262730; color: white; box-shadow: 0 1px 0 #444; }
        .matrix-table th:first-child, .matrix-table td:first-child, .custom-table th:first-child, .custom-table td:first-child { background-color: #0e1117; box-shadow: 1px 0 0 #666; color: white; }
        .matrix-table th:first-child, .custom-table th:first-child { background-color: #262730; box-shadow: 1px 1px 0 #666; }
        .matrix-table td, .custom-table td { border-color: #444; color: white; }
        .matrix-cell-btn, .action-btn { background-color: #1e2127; border-color: #444; color: #ddd; }
        .matrix-cell-btn:hover, .action-btn:hover { background-color: #2a2e37; color: #fff; }
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
        var inputs = pDoc.querySelectorAll('input[aria-label^="hidden_pay_"]');
        if (inputs.length > 0) {
            inputs.forEach(function(input) {
                var wrapper = input.closest('div[data-testid="stTextInput"]');
                if (wrapper) { wrapper.style.position = 'absolute'; wrapper.style.opacity = '0'; wrapper.style.pointerEvents = 'none'; wrapper.style.height = '0px'; wrapper.style.overflow = 'hidden'; }
            });
        } else { setTimeout(hideInput, 100); }
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

def handle_matrix_click():
    key_m = st.session_state.current_pay_mat_key
    payload = st.session_state.get(key_m, "")
    if payload:
        parts = payload.split('|')
        if len(parts) >= 3:
            st.session_state.payment_modal = {"active_lease_id": parts[0], "month": int(parts[1]), "year": int(parts[2])}
        st.session_state[key_m] = ""

def handle_list_action():
    key_l = st.session_state.current_pay_list_key
    val = st.session_state.get(key_l, "")
    if val:
        parts = val.split('|')
        if parts[0].startswith("EDIT_"):
            st.session_state.pay_list_action = 'edit'
            st.session_state.action_pay_list_id = parts[0].replace("EDIT_", "")
        st.session_state[key_l] = ""

def show():
    if "payment_modal" not in st.session_state: st.session_state.payment_modal = None
    if "action_pay_id" not in st.session_state: st.session_state.action_pay_id = None
    if "action_edit_id" not in st.session_state: st.session_state.action_edit_id = None
    if "pay_list_action" not in st.session_state: st.session_state.pay_list_action = None
    if "action_pay_list_id" not in st.session_state: st.session_state.action_pay_list_id = None

    if "current_pay_mat_key" not in st.session_state: st.session_state.current_pay_mat_key = f"hidden_pay_matrix_val_{uuid.uuid4().hex[:8]}"
    if "current_pay_list_key" not in st.session_state: st.session_state.current_pay_list_key = f"hidden_pay_list_val_{uuid.uuid4().hex[:8]}"

    st.text_input("hidden_pay_matrix", key=st.session_state.current_pay_mat_key, label_visibility="collapsed", on_change=handle_matrix_click)
    st.text_input("hidden_pay_list", key=st.session_state.current_pay_list_key, label_visibility="collapsed", on_change=handle_list_action)

    st.header("Καταγραφή Οφειλών & Εισπράξεων")
    
    try:
        leases_df = gsheets_service.fetch_all_leases()
        tenants_df = gsheets_service.fetch_all_tenants()
        properties_df = gsheets_service.fetch_all_properties()
        payments_df = gsheets_service.fetch_all_payments()
    except Exception as e:
        st.error(f"Αδυναμία φόρτωσης δεδομένων: {e}")
        return

    if leases_df.empty:
        st.info("Δεν υπάρχουν ενεργές μισθώσεις.")
        return

    if not payments_df.empty:
        if "For_Month" not in payments_df.columns: payments_df["For_Month"] = ""
        if "For_Year" not in payments_df.columns: payments_df["For_Year"] = ""
        if "Status" not in payments_df.columns: payments_df["Status"] = "Εξοφλήθηκε" 
        if "Description" not in payments_df.columns: payments_df["Description"] = "" 
        
        payments_df['Date_Obj'] = pd.to_datetime(payments_df['Date_Received'], errors='coerce')
        
        def get_m(row):
            if pd.notna(row.get('For_Month')) and str(row.get('For_Month')).strip() != "": return str(row['For_Month']).split('.')[0]
            elif pd.notna(row.get('Date_Obj')): return str(row['Date_Obj'].month)
            return "0"
        def get_y(row):
            if pd.notna(row.get('For_Year')) and str(row.get('For_Year')).strip() != "": return str(row['For_Year']).split('.')[0]
            elif pd.notna(row.get('Date_Obj')): return str(row['Date_Obj'].year)
            return "0"
            
        payments_df['Calc_Month'] = payments_df.apply(get_m, axis=1)
        payments_df['Calc_Year'] = payments_df.apply(get_y, axis=1)
        payments_df['Status'] = payments_df['Status'].fillna('Εξοφλήθηκε').replace('', 'Εξοφλήθηκε')
    else:
        payments_df = pd.DataFrame(columns=['Payment_ID', 'Lease_ID', 'Payment_Type', 'Amount', 'Date_Received', 'Bank_Account', 'For_Month', 'For_Year', 'Status', 'Description', 'Calc_Month', 'Calc_Year'])

    l_opts_all = {}
    lease_to_prop = {}
    lease_to_tenant = {}
    
    for _, r in leases_df.iterrows():
        l_id = str(r.get("Lease_ID", ""))
        p_id = str(r.get("Property_ID", ""))
        p_charact = "-"
        p_match = properties_df[properties_df["Property_ID"] == p_id] if not properties_df.empty else pd.DataFrame()
        if not p_match.empty: p_charact = str(p_match.iloc[0].get('Χαρακτηριστικό', '-'))
        t_names = []
        for tid_clean in [t.strip() for t in str(r.get("Tenant_ID", "")).split(',') if t.strip()]:
            t_match = tenants_df[tenants_df["Tenant_ID"] == tid_clean]
            if not t_match.empty: t_names.append(f"{str(t_match.iloc[0].get('Επώνυμο', ''))} {str(t_match.iloc[0].get('Όνομα', ''))}")
        
        t_display = ' & '.join(t_names) if t_names else 'Άγνωστος'
        l_opts_all[l_id] = f"{t_display} | {p_charact}"
        lease_to_prop[l_id] = p_charact
        lease_to_tenant[l_id] = t_display

    leases_df['Group_Key'] = leases_df['Property_ID'] + "_" + leases_df['Tenant_ID']

    def get_expected_rent_and_lease(group_leases, y, m):
        test_m_y = y * 12 + m
        sorted_leases = group_leases.sort_values(by='Start_Date', ascending=False)
        for _, l in sorted_leases.iterrows():
            try: s_date = datetime.strptime(str(l['Start_Date']), "%Y-%m-%d").date()
            except: continue
            try: e_date = datetime.strptime(str(l['End_Date']), "%Y-%m-%d").date()
            except: e_date = date(2099, 12, 31)
            if s_date.year * 12 + s_date.month <= test_m_y <= e_date.year * 12 + e_date.month:
                rent = pd.to_numeric(str(l.get('Monthly_Rent', '0')).replace(',', '.'), errors='coerce')
                return rent if pd.notna(rent) else 0.0, str(l['Lease_ID'])
        latest = sorted_leases.iloc[0]
        rent = pd.to_numeric(str(latest.get('Monthly_Rent', '0')).replace(',', '.'), errors='coerce')
        return rent if pd.notna(rent) else 0.0, str(latest['Lease_ID'])

    tab_matrix, tab_list = st.tabs(["📊 Πίνακας Ελέγχου", "📋 Ιστορικό Όλων των Εισπράξεων"])

    # =========================================================================
    # --- 1. MATRIX ---
    # =========================================================================
    with tab_matrix:
        current_year = datetime.today().year
        selected_year = st.selectbox("Επιλογή Έτους", [current_year - 1, current_year, current_year + 1, current_year + 2], index=1, key="pay_mat_year_sel")
        st.subheader(f"Κατάσταση Μισθωμάτων & Λογαριασμών - {selected_year}")
        
        months = ["Ιαν", "Φεβ", "Μαρ", "Απρ", "Μάι", "Ιουν", "Ιουλ", "Αυγ", "Σεπ", "Οκτ", "Νοε", "Δεκ"]
        
        html_code = f"""<!DOCTYPE html><html><head><style>{COMMON_CSS}</style></head><body>
        <div class="matrix-wrapper"><table class="matrix-table"><tr><th>Ακίνητο & Ενοικιαστής</th>"""
        for m in months: html_code += f'<th>{m}</th>'
        html_code += '</tr>'

        for g_key, group_leases in leases_df.groupby('Group_Key'):
            l_id_list = group_leases['Lease_ID'].astype(str).tolist()
            first_l = group_leases.iloc[0]
            p_id = str(first_l.get("Property_ID", ""))
            prop_charact = "-"
            if not properties_df.empty:
                p_match = properties_df[properties_df["Property_ID"] == p_id]
                if not p_match.empty: prop_charact = str(p_match.iloc[0].get('Χαρακτηριστικό', '-'))
            t_names = []
            for tid_clean in [t.strip() for t in str(first_l.get("Tenant_ID", "")).split(',') if t.strip()]:
                t_match = tenants_df[tenants_df["Tenant_ID"] == tid_clean]
                if not t_match.empty: t_names.append(f"{str(t_match.iloc[0].get('Επώνυμο', '')).replace('nan','')} {str(t_match.iloc[0].get('Όνομα', '')).replace('nan','')}")
            tenant_name = " & ".join(t_names) if t_names else "Άγνωστος"

            html_code += f'<tr><td>🏠 <strong>{prop_charact}</strong><br>👤 <span style="font-size: 11px; opacity: 0.8;">{tenant_name[:25]}</span></td>'

            for m_idx in range(1, 13):
                expected_rent, active_l_id = get_expected_rent_and_lease(group_leases, selected_year, m_idx)
                p_month = payments_df[(payments_df['Lease_ID'].isin(l_id_list)) & (payments_df['Calc_Month'] == str(m_idx)) & (payments_df['Calc_Year'] == str(selected_year))]
                
                html_code += '<td>'
                click_payload = f"{active_l_id}|{m_idx}|{selected_year}"
                
                if p_month.empty:
                    html_code += f'<button class="matrix-cell-empty" onclick="triggerPython(\'{click_payload}\', \'hidden_pay_matrix\')">❌ Κενό</button>'
                else:
                    for p_type in p_month['Payment_Type'].unique():
                        type_data = p_month[p_month['Payment_Type'] == p_type]
                        is_pending = not type_data[type_data['Status'] == 'Εκκρεμεί'].empty
                        
                        if p_type == 'Ενοίκιο':
                            rent_paid_amt = pd.to_numeric(type_data[type_data['Status'] == 'Εξοφλήθηκε']['Amount'].astype(str).str.replace(',', '.'), errors='coerce').sum()
                            if is_pending: btn_text = f"Ενοίκιο<br>⚠️ Εκκρ."
                            elif rent_paid_amt < expected_rent: btn_text = f"Ενοίκιο<br>⚠️ {rent_paid_amt:.0f}€"
                            else: btn_text = f"Ενοίκιο<br>✅ Εξοφλ."
                        else:
                            short_type = p_type[:5] + "." if len(p_type) > 5 else p_type
                            btn_text = f"{short_type}<br>⚠️ Εκκρ." if is_pending else f"{short_type}<br>✅ Εξοφλ."
                        html_code += f'<button class="matrix-cell-btn" onclick="triggerPython(\'{click_payload}\', \'hidden_pay_matrix\')">{btn_text}</button>'
                html_code += '</td>'
            html_code += '</tr>'
            
        html_code += f"</table></div>{COMMON_JS}</body></html>"
        components.html(html_code, height=600, scrolling=True)

        if st.session_state.payment_modal:
            m_info = st.session_state.payment_modal
            active_l_id = m_info["active_lease_id"]
            m_idx = m_info["month"]
            selected_year = m_info["year"]
            
            active_l_row = leases_df[leases_df['Lease_ID'] == active_l_id]
            if not active_l_row.empty:
                p_id = str(active_l_row.iloc[0].get('Property_ID', ''))
                t_id = str(active_l_row.iloc[0].get('Tenant_ID', ''))
                group_leases = leases_df[leases_df['Group_Key'] == (p_id + "_" + t_id)]
                l_id_list = group_leases['Lease_ID'].astype(str).tolist()
                expected_rent, _ = get_expected_rent_and_lease(group_leases, selected_year, m_idx)
                
                p_match = properties_df[properties_df["Property_ID"] == p_id] if not properties_df.empty else pd.DataFrame()
                prop_charact = str(p_match.iloc[0].get('Χαρακτηριστικό', '-')) if not p_match.empty else "-"
                
                t_names = []
                for tid_clean in [t.strip() for t in t_id.split(',') if t.strip()]:
                    t_match = tenants_df[tenants_df["Tenant_ID"] == tid_clean]
                    if not t_match.empty: t_names.append(f"{str(t_match.iloc[0].get('Επώνυμο', '')).replace('nan','')} {str(t_match.iloc[0].get('Όνομα', '')).replace('nan','')}")
                tenant_name = " & ".join(t_names) if t_names else "Άγνωστος"
            else:
                l_id_list = [active_l_id]; expected_rent, prop_charact, tenant_name = 0.0, "-", "-"

            st.markdown("---")
            col_t, col_b = st.columns([4, 1])
            with col_t:
                st.markdown(f"### ⚙️ Διαχείριση Μήνα: **{months[m_idx-1]} {selected_year}**")
                st.caption(f"🏠 {prop_charact} | 👤 {tenant_name}")
            with col_b:
                if st.button("❌ Κλείσιμο", use_container_width=True, key="mat_btn_close"):
                    st.session_state.payment_modal = None
                    st.rerun()

            p_month_data = payments_df[(payments_df['Lease_ID'].isin(l_id_list)) & (payments_df['Calc_Month'] == str(m_idx)) & (payments_df['Calc_Year'] == str(selected_year))]
            
            st.markdown("#### 📋 Καταχωρημένες Οφειλές & Εισπράξεις")
            if p_month_data.empty: 
                st.info("Δεν υπάρχει καμία καταχώρηση για αυτόν τον μήνα.")
            else:
                for _, p_row in p_month_data.iterrows():
                    pid = p_row['Payment_ID']
                    amt = pd.to_numeric(str(p_row['Amount']).replace(',', '.'), errors='coerce')
                    if pd.isna(amt): amt = 0.0
                    is_pending = (str(p_row.get('Status', '')) == 'Εκκρεμεί')
                    desc_text = str(p_row.get('Description', '')).replace('nan','')
                    display_type = f"{p_row['Payment_Type']} ({desc_text})" if desc_text else p_row['Payment_Type']
                    
                    with st.container(border=True):
                        if st.session_state.action_pay_id == pid:
                            st.write(f"💳 **Ολοκλήρωση Πληρωμής:** {display_type} | {amt:.2f}€")
                            pay_c1, pay_c2, pay_c3, pay_c4 = st.columns([2, 2, 1, 1])
                            pay_date = pay_c1.date_input("Ημ/νία Εξόφλησης", value=date.today(), key=f"d_pay_{pid}")
                            pay_bank = pay_c2.selectbox("Τράπεζα / Τρόπος", ["Εθνική Τράπεζα", "Eurobank", "Alpha Bank", "Τράπεζα Πειραιώς", "Μετρητά", "Άλλο"], key=f"b_pay_{pid}")
                            
                            if pay_c3.button("💾 Αποθ.", key=f"s_pay_{pid}", type="primary", use_container_width=True):
                                try:
                                    new_row = [pid, p_row['Lease_ID'], p_row['Payment_Type'], p_row['Amount'], pay_date.strftime("%Y-%m-%d"), pay_bank, p_row['For_Month'], p_row['For_Year'], "Εξοφλήθηκε", p_row.get('Description', '')]
                                    gsheets_service.update_payment(pid, new_row)
                                    st.success("Εξοφλήθηκε επιτυχώς!")
                                    time.sleep(1.5)
                                    st.session_state.action_pay_id = None
                                    st.rerun()
                                except Exception as e: st.error(f"Σφάλμα: {e}")
                            if pay_c4.button("Άκυρο", key=f"c_pay_{pid}", use_container_width=True):
                                st.session_state.action_pay_id = None; st.rerun()
                        
                        elif st.session_state.action_edit_id == pid:
                            st.write(f"✏️ **Επεξεργασία Εγγραφής**")
                            e_c1, e_c2, e_c3 = st.columns(3)
                            type_opts = ["Ενοίκιο", "Νερό", "Κοινόχρηστα", "Ρεύμα", "Άλλο"]
                            e_type = e_c1.selectbox("Είδος", type_opts, index=type_opts.index(p_row['Payment_Type']) if p_row['Payment_Type'] in type_opts else 0, key=f"et_{pid}")
                            e_amt = e_c2.text_input("Ποσό (€)", value=str(p_row['Amount']).replace('.', ','), key=f"ea_{pid}")
                            e_status = e_c3.selectbox("Κατάσταση", ["Εκκρεμεί", "Εξοφλήθηκε"], index=0 if is_pending else 1, key=f"es_{pid}")
                            
                            e_desc = st.text_input("Περιγραφή (προαιρετικό)", value=desc_text, key=f"edesc_{pid}")
                            
                            e_c4, e_c5, e_c6, e_c7 = st.columns([2, 2, 1, 1])
                            try: default_date = datetime.strptime(str(p_row['Date_Received']), "%Y-%m-%d").date()
                            except: default_date = date.today()
                            e_date = e_c4.date_input("Ημ/νία", value=default_date, key=f"ed_{pid}")
                            
                            bank_opts = ["Εθνική Τράπεζα", "Eurobank", "Alpha Bank", "Τράπεζα Πειραιώς", "Μετρητά", "Άλλο", "Εκκρεμεί"]
                            e_bank = e_c5.selectbox("Τράπεζα", bank_opts, index=bank_opts.index(p_row['Bank_Account']) if p_row['Bank_Account'] in bank_opts else 0, key=f"eb_{pid}")
                            
                            if e_c6.button("💾 Αποθ.", key=f"s_edit_{pid}", type="primary", use_container_width=True):
                                try:
                                    final_bank = "Εκκρεμεί" if e_status == "Εκκρεμεί" else e_bank
                                    new_row = [pid, p_row['Lease_ID'], e_type, e_amt, e_date.strftime("%Y-%m-%d"), final_bank, p_row['For_Month'], p_row['For_Year'], e_status, e_desc]
                                    gsheets_service.update_payment(pid, new_row)
                                    st.success("Αποθηκεύτηκε!")
                                    time.sleep(1.5)
                                    st.session_state.action_edit_id = None
                                    st.rerun()
                                except Exception as e: st.error(f"Σφάλμα: {e}")
                            if e_c7.button("Άκυρο", key=f"c_edit_{pid}", use_container_width=True):
                                st.session_state.action_edit_id = None; st.rerun()

                        else:
                            icon = "⚠️" if is_pending else "✅"
                            pc1, pc2, pc3, pc4 = st.columns([3, 2, 2, 3])
                            pc1.write(f"**{icon} {display_type}** | {amt:.2f}€")
                            if is_pending:
                                pc2.write(f"Έκδοση: {p_row['Date_Received']}")
                                pc3.write("**Εκκρεμεί**")
                            else:
                                pc2.write(f"Πληρωμή: {p_row['Date_Received']}")
                                pc3.write(f"🏦 {p_row['Bank_Account']}")
                            
                            bc1, bc2, bc3 = pc4.columns(3)
                            if is_pending:
                                if bc1.button("💳 Εξόφληση", key=f"btn_p_{pid}"):
                                    st.session_state.action_pay_id = pid; st.session_state.action_edit_id = None; st.rerun()
                            if bc2.button("✏️ Επεξ.", key=f"btn_e_{pid}"):
                                st.session_state.action_edit_id = pid; st.session_state.action_pay_id = None; st.rerun()
                            if bc3.button("🗑️ Διαγρ.", key=f"btn_d_{pid}"):
                                gsheets_service.delete_payment(pid)
                                st.success("Διαγράφηκε!")
                                time.sleep(1.5)
                                st.rerun()

            st.markdown("#### ➕ Προσθήκη Νέας Καταχώρησης")
            with st.form("add_monthly_payment_form"):
                fc1, fc2, fc3 = st.columns([2, 2, 2])
                with fc1: p_type = st.selectbox("Είδος *", ["Ενοίκιο", "Νερό", "Κοινόχρηστα", "Ρεύμα", "Άλλο"], key="mat_new_type")
                with fc2: 
                    rent_paid = pd.to_numeric(p_month_data[p_month_data['Payment_Type'] == 'Ενοίκιο']['Amount'].astype(str).str.replace(',', '.'), errors='coerce').sum() if not p_month_data.empty else 0.0
                    default_amt = str(max(0, expected_rent - rent_paid)).replace('.', ',') if rent_paid < expected_rent else "0"
                    p_amt = st.text_input("Ποσό (€) *", value=default_amt, key="mat_new_amt")
                with fc3: p_status = st.radio("Κατάσταση *", ["Εκκρεμεί", "Εξοφλήθηκε"], index=1, key="mat_new_stat")
                
                p_desc = st.text_input("Περιγραφή (προαιρετικό)", key="mat_new_desc")
                
                hc1, hc2 = st.columns(2)
                with hc1: p_date = st.date_input("Ημερομηνία *", value=date.today(), key="mat_new_date")
                with hc2: 
                    is_exof = "Εξοφλήθηκε" in p_status
                    p_bank = st.selectbox("Τράπεζα / Τρόπος", ["Εθνική Τράπεζα", "Eurobank", "Alpha Bank", "Τράπεζα Πειραιώς", "Μετρητά", "Άλλο"], key="mat_new_bank") if is_exof else "Εκκρεμεί"
                
                if st.form_submit_button("Αποθήκευση", use_container_width=True):
                    amt_val = pd.to_numeric(p_amt.replace(',', '.'), errors='coerce')
                    if pd.isna(amt_val): amt_val = 0.0
                    if amt_val > 0:
                        try:
                            clean_status = "Εξοφλήθηκε" if is_exof else "Εκκρεμεί"
                            gsheets_service.add_payment([f"PAY-{uuid.uuid4().hex[:6].upper()}", active_l_id, p_type, p_amt, p_date.strftime("%Y-%m-%d"), p_bank, str(m_idx), str(selected_year), clean_status, p_desc])
                            st.success("Καταχωρήθηκε!")
                            time.sleep(1.5)
                            st.rerun() 
                        except Exception as e: st.error(f"Σφάλμα: {e}")
                    else: st.warning("Παρακαλώ εισάγετε έγκυρο ποσό.")

    # =========================================================================
    # --- 2. ΙΣΤΟΡΙΚΟ ΟΛΩΝ ΤΩΝ ΕΙΣΠΡΑΞΕΩΝ ---
    # =========================================================================
    with tab_list:
        if st.session_state.pay_list_action == 'new':
            st.markdown("### ➕ Προσθήκη Νέας Είσπραξης / Οφειλής")
            col_b, _ = st.columns([1, 4])
            if col_b.button("⬅️ Επιστροφή", key="back_pay_list_new", use_container_width=True):
                st.session_state.pay_list_action = None
                st.rerun()

            with st.form("new_global_payment_form", clear_on_submit=True):
                l_keys = list(l_opts_all.keys())
                sel_l = st.selectbox("Μίσθωση / Ακίνητο *", options=l_keys, format_func=lambda x: l_opts_all.get(x, x), key="glb_new_lease")
                
                c1, c2, c3 = st.columns(3)
                with c1: p_type = st.selectbox("Είδος *", ["Ενοίκιο", "Νερό", "Κοινόχρηστα", "Ρεύμα", "Άλλο"], key="glb_new_type")
                with c2: p_amt = st.text_input("Ποσό (€) *", value="0", key="glb_new_amt")
                with c3: p_status = st.selectbox("Κατάσταση *", ["Εξοφλήθηκε", "Εκκρεμεί"], key="glb_new_stat")
                
                p_desc = st.text_input("Περιγραφή (προαιρετικό)", key="glb_new_desc")
                
                c4, c5 = st.columns(2)
                with c4: p_date = st.date_input("Ημερομηνία *", value=date.today(), key="glb_new_date")
                bank_opts = ["Εθνική Τράπεζα", "Eurobank", "Alpha Bank", "Τράπεζα Πειραιώς", "Μετρητά", "Άλλο", "Εκκρεμεί"]
                with c5: p_bank = st.selectbox("Τράπεζα / Τρόπος", bank_opts, index=0 if p_status == "Εξοφλήθηκε" else 6, key="glb_new_bank")
                
                c6, c7 = st.columns(2)
                with c6: for_m = st.selectbox("Για Μήνα", list(range(1, 13)), index=datetime.today().month - 1, key="glb_new_m")
                with c7: for_y = st.selectbox("Για Έτος", [datetime.today().year - 1, datetime.today().year, datetime.today().year + 1], index=1, key="glb_new_y")
                
                if st.form_submit_button("Αποθήκευση Είσπραξης", type="primary", use_container_width=True):
                    amt_val = pd.to_numeric(p_amt.replace(',', '.'), errors='coerce')
                    if pd.isna(amt_val) or amt_val <= 0:
                        st.warning("Παρακαλώ εισάγετε έγκυρο ποσό.")
                    else:
                        try:
                            pay_id = f"PAY-{uuid.uuid4().hex[:6].upper()}"
                            gsheets_service.add_payment([pay_id, sel_l, p_type, p_amt, p_date.strftime("%Y-%m-%d"), p_bank, str(for_m), str(for_y), p_status, p_desc])
                            st.success("Η είσπραξη καταχωρήθηκε επιτυχώς!")
                            time.sleep(1.5)
                            st.session_state.pay_list_action = None
                            st.rerun()
                        except Exception as e: st.error(f"Σφάλμα: {e}")

        elif st.session_state.pay_list_action == 'edit':
            st.markdown("### ✏️ Επεξεργασία Είσπραξης / Οφειλής")
            col_b, _ = st.columns([1, 4])
            if col_b.button("⬅️ Επιστροφή", key="back_pay_list_edit", use_container_width=True):
                st.session_state.pay_list_action = None
                st.rerun()

            sel_pid = st.session_state.action_pay_list_id
            sel_pay = payments_df[payments_df["Payment_ID"] == sel_pid].iloc[0]
            
            l_keys = list(l_opts_all.keys())
            try: l_idx = l_keys.index(str(sel_pay.get("Lease_ID", "")))
            except: l_idx = 0
            
            try: pay_date = datetime.strptime(str(sel_pay.get("Date_Received", "")), "%Y-%m-%d").date()
            except: pay_date = date.today()

            with st.form("edit_global_payment_form"):
                e_lease = st.selectbox("Μίσθωση / Ακίνητο *", options=l_keys, index=l_idx, format_func=lambda x: l_opts_all.get(x, x), key=f"glb_e_l_{sel_pid}")
                
                type_opts = ["Ενοίκιο", "Νερό", "Κοινόχρηστα", "Ρεύμα", "Άλλο"]
                curr_type = str(sel_pay.get("Payment_Type", ""))
                
                c1, c2, c3 = st.columns(3)
                with c1: e_type = st.selectbox("Είδος *", type_opts, index=type_opts.index(curr_type) if curr_type in type_opts else 0, key=f"glb_e_t_{sel_pid}")
                with c2: e_amt = st.text_input("Ποσό (€) *", value=str(sel_pay.get("Amount", "")).replace('.', ','), key=f"glb_e_a_{sel_pid}")
                curr_status = str(sel_pay.get("Status", "Εξοφλήθηκε"))
                with c3: e_status = st.selectbox("Κατάσταση *", ["Εξοφλήθηκε", "Εκκρεμεί"], index=0 if curr_status == "Εξοφλήθηκε" else 1, key=f"glb_e_s_{sel_pid}")
                
                e_desc = st.text_input("Περιγραφή (προαιρετικό)", value=str(sel_pay.get("Description", "")).replace('nan',''), key=f"glb_e_desc_{sel_pid}")
                
                c4, c5 = st.columns(2)
                with c4: e_date = st.date_input("Ημερομηνία *", value=pay_date, key=f"glb_e_d_{sel_pid}")
                bank_opts = ["Εθνική Τράπεζα", "Eurobank", "Alpha Bank", "Τράπεζα Πειραιώς", "Μετρητά", "Άλλο", "Εκκρεμεί"]
                curr_bank = str(sel_pay.get("Bank_Account", ""))
                with c5: e_bank = st.selectbox("Τράπεζα / Τρόπος", bank_opts, index=bank_opts.index(curr_bank) if curr_bank in bank_opts else 0, key=f"glb_e_b_{sel_pid}")
                
                c6, c7 = st.columns(2)
                try: m_idx_val = int(str(sel_pay.get("Calc_Month", "1")).split('.')[0]) - 1
                except: m_idx_val = 0
                with c6: e_for_m = st.selectbox("Για Μήνα", list(range(1, 13)), index=max(0, min(11, m_idx_val)), key=f"glb_e_m_{sel_pid}")
                
                try: curr_y_val = int(str(sel_pay.get("Calc_Year", datetime.today().year)).split('.')[0])
                except: curr_y_val = datetime.today().year
                y_options = [curr_y_val - 2, curr_y_val - 1, curr_y_val, curr_y_val + 1]
                with c7: e_for_y = st.selectbox("Για Έτος", y_options, index=y_options.index(curr_y_val), key=f"glb_e_y_{sel_pid}")

                upd_p_btn = st.form_submit_button("Αποθήκευση Αλλαγών", type="primary", use_container_width=True)

            if st.button("🗑️ Οριστική Διαγραφή Είσπραξης", use_container_width=True, key=f"glb_del_{sel_pid}"):
                try:
                    gsheets_service.delete_payment(sel_pid)
                    st.success("Διαγράφηκε επιτυχώς!")
                    time.sleep(1.5)
                    st.session_state.pay_list_action = None
                    st.rerun()
                except Exception as e: st.error(f"Σφάλμα: {e}")

            if upd_p_btn:
                amt_val = pd.to_numeric(e_amt.replace(',', '.'), errors='coerce')
                if pd.isna(amt_val) or amt_val <= 0:
                    st.warning("Παρακαλώ εισάγετε έγκυρο ποσό.")
                else:
                    try:
                        new_row = [sel_pid, e_lease, e_type, e_amt, e_date.strftime("%Y-%m-%d"), e_bank, str(e_for_m), str(e_for_y), e_status, e_desc]
                        gsheets_service.update_payment(sel_pid, new_row)
                        st.success("Οι αλλαγές αποθηκεύτηκαν!")
                        time.sleep(1.5)
                        st.session_state.pay_list_action = None
                        st.rerun()
                    except Exception as e: st.error(f"Σφάλμα: {e}")

        else:
            st.subheader("Ιστορικό Εισπράξεων & Οφειλών")
            
            if payments_df.empty: 
                st.info("Δεν έχουν καταγραφεί εισπράξεις.")
            else:
                fc1, fc2, fc3 = st.columns(3)
                fc4, fc5 = st.columns(2)
                
                all_years = set()
                for _, r in payments_df.iterrows():
                    y_val = str(r.get("Calc_Year", "")).strip()
                    if y_val and y_val != "0": all_years.add(y_val)
                sorted_years = ["Όλα τα έτη"] + sorted(list(all_years), reverse=True)
                sel_year = fc1.selectbox("Επιλογή Έτους", sorted_years, key="pay_filter_year")

                unique_props = set(lease_to_prop.values())
                all_props_opts = ["Όλα τα ακίνητα"] + sorted(list(unique_props))
                sel_prop = fc2.selectbox("Ακίνητο", all_props_opts, key="pay_filter_prop")

                unique_tenants = set(lease_to_tenant.values())
                all_tenants_opts = ["Όλοι οι μισθωτές"] + sorted(list(unique_tenants))
                sel_tenant = fc3.selectbox("Μισθωτής", all_tenants_opts, key="pay_filter_tenant")

                all_types = ["Όλα τα είδη", "Ενοίκιο", "Νερό", "Κοινόχρηστα", "Ρεύμα", "Άλλο"]
                sel_type = fc4.selectbox("Είδος", all_types, key="pay_filter_type")
                
                all_statuses = ["Όλες", "Εξοφλήθηκε", "Εκκρεμεί"]
                sel_status = fc5.selectbox("Κατάσταση", all_statuses, key="pay_filter_status")
                
                st.write("") 

                pay_list_data = []
                for _, row in payments_df.iterrows():
                    p_type = str(row.get("Payment_Type", ""))
                    row_y = str(row.get("Calc_Year", "")).strip()
                    status_val = str(row.get("Status", "Εξοφλήθηκε"))
                    l_id = str(row.get("Lease_ID", ""))
                    
                    prop_name = lease_to_prop.get(l_id, "Άγνωστο")
                    tenant_name = lease_to_tenant.get(l_id, "Άγνωστος")
                    
                    if sel_year != "Όλα τα έτη" and row_y != sel_year: continue
                    if sel_prop != "Όλα τα ακίνητα" and prop_name != sel_prop: continue
                    if sel_tenant != "Όλοι οι μισθωτές" and tenant_name != sel_tenant: continue
                    if sel_type != "Όλα τα είδη" and p_type != sel_type: continue
                    if sel_status != "Όλες" and status_val != sel_status: continue

                    amt_val = pd.to_numeric(str(row.get('Amount', '0')).replace(',', '.'), errors='coerce')
                    if pd.isna(amt_val): amt_val = 0.0
                    
                    d_text = str(row.get("Description", "")).replace('nan','')
                    cat_display = f"{p_type}<br><span style='font-size: 11px; color: #555;'>({d_text})</span>" if d_text else p_type
                    
                    pay_list_data.append({
                        "Payment_ID": str(row.get("Payment_ID", "")),
                        "Μίσθωση / Ακίνητο": l_opts_all.get(str(row.get("Lease_ID", "")), "Διαγραμμένη Μίσθωση"),
                        "Ημερομηνία": str(row.get("Date_Received", "")),
                        "Μήνας / Έτος": f"{row.get('Calc_Month', '-')} / {row.get('Calc_Year', '-')}",
                        "Είδος": cat_display,
                        "Ποσό": f"{amt_val:.2f} €".replace('.', ','),
                        "Κατάσταση": "✅ Εξοφλήθηκε" if status_val == "Εξοφλήθηκε" else "⚠️ Εκκρεμεί",
                        "Μέθοδος": str(row.get("Bank_Account", ""))
                    })
                
                if not pay_list_data:
                    st.info("Δεν βρέθηκαν εγγραφές με τα επιλεγμένα κριτήρια.")
                else:
                    html_code = f"""
                    <!DOCTYPE html><html><head><style>{COMMON_CSS}</style></head><body>
                    <div class="table-container">
                        <table id="pay-table" class="custom-table">
                            <thead>
                                <tr>
                                    <th onclick="sortTable('pay-table', 0)">Μίσθωση / Ακίνητο ⇕</th>
                                    <th onclick="sortTable('pay-table', 1)">Ημερομηνία ⇕</th>
                                    <th onclick="sortTable('pay-table', 2)">Μήνας / Έτος ⇕</th>
                                    <th onclick="sortTable('pay-table', 3)">Είδος ⇕</th>
                                    <th onclick="sortTable('pay-table', 4)">Ποσό ⇕</th>
                                    <th onclick="sortTable('pay-table', 5)">Κατάσταση ⇕</th>
                                    <th onclick="sortTable('pay-table', 6)">Μέθοδος ⇕</th>
                                    <th>Ενέργεια</th>
                                </tr>
                            </thead>
                            <tbody>
                    """
                    for item in pay_list_data[::-1]:
                        html_code += f"""
                                <tr>
                                    <td>{item['Μίσθωση / Ακίνητο']}</td>
                                    <td>{item['Ημερομηνία']}</td>
                                    <td>{item['Μήνας / Έτος']}</td>
                                    <td>{item['Είδος']}</td>
                                    <td><strong>{item['Ποσό']}</strong></td>
                                    <td>{item['Κατάσταση']}</td>
                                    <td>{item['Μέθοδος']}</td>
                                    <td><button class="action-btn" onclick="triggerPython('EDIT_{item['Payment_ID']}', 'hidden_pay_list')">✏️ Επεξ.</button></td>
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

            st.write("")
            if st.button("➕ Προσθήκη Νέας Είσπραξης", type="primary", use_container_width=True, key="btn_add_new_pay"):
                st.session_state.pay_list_action = 'new'
                st.rerun()
