import streamlit as st
import gsheets_service
import uuid
import pandas as pd
from datetime import date, datetime
import streamlit.components.v1 as components

COMMON_CSS = """
<style>
    /* CSS ΓΙΑ ΤΟΝ ΕΝΙΑΙΟ HTML ΠΙΝΑΚΑ */
    html, body { height: 100%; margin: 0; padding: 0; overflow: hidden; font-family: sans-serif; }
    .matrix-wrapper {
        height: 100%;
        overflow: auto;
        border: 1px solid #ddd;
        border-radius: 8px;
        box-sizing: border-box;
    }
    .matrix-table {
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        font-size: 13px;
        background: white;
        min-width: 950px; 
    }
    .matrix-table th, .matrix-table td {
        padding: 6px;
        text-align: center;
        border-bottom: 1px solid #ddd;
        border-right: 1px solid #ddd;
    }
    .matrix-table th {
        background-color: #f0f2f6;
        color: #31333F;
        position: sticky;
        top: 0;
        z-index: 4;
        box-shadow: 0 1px 0 #ddd;
        padding: 10px 6px;
    }
    .matrix-table th:first-child, .matrix-table td:first-child {
        position: sticky;
        left: 0;
        background-color: #ffffff;
        z-index: 5;
        text-align: left;
        min-width: 140px;
        max-width: 220px;
        box-shadow: 1px 0 0 #bbb;
    }
    .matrix-table th:first-child {
        z-index: 6;
        box-shadow: 1px 1px 0 #bbb;
    }
    
    .matrix-cell-btn {
        display: block; width: 100%; text-align: center; color: #31333F;
        padding: 6px; border-radius: 4px; background-color: #f8f9fa;
        border: 1px solid #e9ecef; margin-bottom: 4px; font-weight: 500;
        cursor: pointer; transition: all 0.2s; font-size: 12px;
    }
    .matrix-cell-btn:hover { background-color: #e2e6ea; border-color: #dae0e5; color: #000; }
    .matrix-cell-empty {
        display: block; width: 100%; text-align: center; color: #6c757d;
        padding: 6px; cursor: pointer; background: none; border: none; font-size: 12px;
    }
    
    @media (prefers-color-scheme: dark) {
        .matrix-wrapper { border-color: #444; }
        .matrix-table { background: #0e1117; color: white; }
        .matrix-table th { background-color: #262730; color: white; box-shadow: 0 1px 0 #444; }
        .matrix-table th:first-child, .matrix-table td:first-child { background-color: #0e1117; box-shadow: 1px 0 0 #666; }
        .matrix-table th:first-child { box-shadow: 1px 1px 0 #666; }
        .matrix-table td { border-color: #444; color: white; }
        .matrix-cell-btn { background-color: #1e2127; border-color: #444; color: #ddd; }
        .matrix-cell-btn:hover { background-color: #2a2e37; color: #fff; }
    }
</style>
"""

# CALLBACK ΠΟΥ ΛΥΝΕΙ ΤΟ ΣΦΑΛΜΑ TOY STREAMLIT
def handle_matrix_click():
    payload = st.session_state.hidden_click_val
    if payload != "":
        parts = payload.split('|')
        if len(parts) >= 3:
            st.session_state.payment_modal = {
                "active_lease_id": parts[0],
                "month": int(parts[1]),
                "year": int(parts[2])
            }
        # Ασφαλής μηδενισμός ΜΕΣΑ στο callback!
        st.session_state.hidden_click_val = ""

def show():
    # --- ΚΡΥΦΟ ΠΕΔΙΟ ΓΙΑ ΤΗ ΛΗΨΗ ΚΛΙΚ ΑΠΟ ΤΗ JAVASCRIPT ---
    st.text_input("hidden_click", key="hidden_click_val", label_visibility="collapsed", on_change=handle_matrix_click)
    
    st.markdown(COMMON_CSS, unsafe_allow_html=True)
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

    # --- ΠΡΟΕΤΟΙΜΑΣΙΑ ΔΕΔΟΜΕΝΩΝ ΠΛΗΡΩΜΩΝ ---
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

    if "payment_modal" not in st.session_state: st.session_state.payment_modal = None
    if "action_pay_id" not in st.session_state: st.session_state.action_pay_id = None
    if "action_edit_id" not in st.session_state: st.session_state.action_edit_id = None

    # --- ΕΞΥΠΝΗ ΟΜΑΔΟΠΟΙΗΣΗ ΜΙΣΘΩΣΕΩΝ ---
    leases_df['Group_Key'] = leases_df['Property_ID'] + "_" + leases_df['Tenant_ID']

    def get_expected_rent_and_lease(group_leases, y, m):
        test_m_y = y * 12 + m
        sorted_leases = group_leases.sort_values(by='Start_Date', ascending=False)
        for _, l in sorted_leases.iterrows():
            try: s_date = datetime.strptime(str(l['Start_Date']), "%Y-%m-%d").date()
            except: continue
            try: e_date = datetime.strptime(str(l['End_Date']), "%Y-%m-%d").date()
            except: e_date = date(2099, 12, 31)
            
            start_m_y = s_date.year * 12 + s_date.month
            end_m_y = e_date.year * 12 + e_date.month
            
            if start_m_y <= test_m_y <= end_m_y:
                rent = pd.to_numeric(str(l.get('Monthly_Rent', '0')).replace(',', '.'), errors='coerce')
                return rent if pd.notna(rent) else 0.0, str(l['Lease_ID'])
                
        latest = sorted_leases.iloc[0]
        rent = pd.to_numeric(str(latest.get('Monthly_Rent', '0')).replace(',', '.'), errors='coerce')
        return rent if pd.notna(rent) else 0.0, str(latest['Lease_ID'])

    tab_matrix, tab_list, tab_edit = st.tabs(["📊 Πίνακας Ελέγχου", "📋 Ιστορικό Όλων των Εισπράξεων", "✏️ Επεξεργασία (Γενική)"])

    # =========================================================================
    # --- 1. MATRIX (ΕΤΗΣΙΑ ΕΠΙΣΚΟΠΗΣΗ ME ΕΞΥΠΝΟ HTML TABLE) ---
    # =========================================================================
    with tab_matrix:
        current_year = datetime.today().year
        selected_year = st.selectbox("Επιλογή Έτους", [current_year - 1, current_year, current_year + 1, current_year + 2], index=1)
        st.subheader(f"Κατάσταση Μισθωμάτων & Λογαριασμών - {selected_year}")
        st.caption("Αγγίξτε ένα κελί (μήνα) για να προβάλετε, να εξοφλήσετε ή να προσθέσετε εισπράξεις.")

        months = ["Ιαν", "Φεβ", "Μαρ", "Απρ", "Μάι", "Ιουν", "Ιουλ", "Αυγ", "Σεπ", "Οκτ", "Νοε", "Δεκ"]
        
        # --- ΚΑΤΑΣΚΕΥΗ HTML ΚΩΔΙΚΑ ΓΙΑ ΤΟΝ ΠΙΝΑΚΑ ---
        html_code = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <style>
            /* Το CSS έχει ήδη περαστεί μέσω της Python */
        </style>
        </head>
        <body>
        <div class="matrix-wrapper">
            <table class="matrix-table">
                <tr><th>Ακίνητο & Ενοικιαστής</th>
        """
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
                click_args = f"'{active_l_id}', {m_idx}, {selected_year}"
                
                if p_month.empty:
                    html_code += f'<button class="matrix-cell-empty" onclick="triggerPython({click_args})">❌ Κενό</button>'
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
                                
                        html_code += f'<button class="matrix-cell-btn" onclick="triggerPython({click_args})">{btn_text}</button>'
                html_code += '</td>'
            html_code += '</tr>'
            
        html_code += """
            </table>
        </div>
        <script>
            // JS που βρίσκει το κρυφό text_input και το "εξαφανίζει" εντελώς
            (function hideInput() {
                var pDoc = window.parent.document;
                var inputs = pDoc.querySelectorAll('input[aria-label="hidden_click"]');
                if (inputs.length > 0) {
                    inputs.forEach(function(input) {
                        var wrapper = input.closest('div[data-testid="stTextInput"]');
                        if (wrapper) wrapper.style.display = 'none';
                    });
                } else {
                    setTimeout(hideInput, 100);
                }
            })();

            // Αθόρυβη αποστολή του κλικ στην Python!
            function triggerPython(lid, m, y) {
                var payload = lid + '|' + m + '|' + y + '|' + Date.now();
                var pDoc = window.parent.document;
                var input = pDoc.querySelector('input[aria-label="hidden_click"]');
                if(input) {
                    var nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    nativeSetter.call(input, payload);
                    input.dispatchEvent(new Event('input', {bubbles: true}));
                    input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', keyCode: 13, which: 13, bubbles: true}));
                }
            }
        </script>
        </body>
        </html>
        """

        # Υπολογισμός δυναμικού ύψους για να μην περισσεύει κενός χώρος
        num_properties = len(leases_df['Group_Key'].unique())
        table_height = max(150, min(100 + num_properties * 65, 650))

        # Εμφάνιση του πίνακα
        components.html(html_code, height=table_height, scrolling=False)

        # ==========================================
        # --- ΠΑΡΑΘΥΡΟ ΔΙΑΧΕΙΡΙΣΗΣ ΜΗΝΑ (MODAL) ---
        # ==========================================
        if st.session_state.payment_modal:
            m_info = st.session_state.payment_modal
            active_l_id = m_info["active_lease_id"]
            m_idx = m_info["month"]
            selected_year = m_info["year"]
            
            # Υπολογισμός Δεδομένων Modal
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
                if st.button("❌ Κλείσιμο", use_container_width=True):
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
                        # --- ΠΛΗΡΩΜΗ ---
                        if st.session_state.action_pay_id == pid:
                            st.write(f"💳 **Ολοκλήρωση Πληρωμής:** {display_type} | {amt:.2f}€")
                            pay_c1, pay_c2, pay_c3, pay_c4 = st.columns([2, 2, 1, 1])
                            pay_date = pay_c1.date_input("Ημ/νία Εξόφλησης", value=date.today(), key=f"d_pay_{pid}")
                            pay_bank = pay_c2.selectbox("Τράπεζα / Τρόπος", ["Εθνική Τράπεζα", "Eurobank", "Alpha Bank", "Τράπεζα Πειραιώς", "Μετρητά", "Άλλο"], key=f"b_pay_{pid}")
                            
                            st.write("") 
                            if pay_c3.button("💾 Αποθήκευση", key=f"s_pay_{pid}", type="primary", use_container_width=True):
                                try:
                                    new_row = [pid, p_row['Lease_ID'], p_row['Payment_Type'], p_row['Amount'], pay_date.strftime("%Y-%m-%d"), pay_bank, p_row['For_Month'], p_row['For_Year'], "Εξοφλήθηκε", p_row.get('Description', '')]
                                    gsheets_service.update_payment(pid, new_row)
                                    st.session_state.action_pay_id = None; st.rerun()
                                except Exception as e: st.error(f"Σφάλμα: {e}")
                            if pay_c4.button("Άκυρο", key=f"c_pay_{pid}", use_container_width=True):
                                st.session_state.action_pay_id = None; st.rerun()
                        
                        # --- ΕΠΕΞΕΡΓΑΣΙΑ (INLINE) ---
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
                            
                            st.write("")
                            if e_c6.button("💾 Αποθ.", key=f"s_edit_{pid}", type="primary", use_container_width=True):
                                try:
                                    final_bank = "Εκκρεμεί" if e_status == "Εκκρεμεί" else e_bank
                                    new_row = [pid, p_row['Lease_ID'], e_type, e_amt, e_date.strftime("%Y-%m-%d"), final_bank, p_row['For_Month'], p_row['For_Year'], e_status, e_desc]
                                    gsheets_service.update_payment(pid, new_row)
                                    st.session_state.action_edit_id = None; st.rerun()
                                except Exception as e: st.error(f"Σφάλμα: {e}")
                            if e_c7.button("Άκυρο", key=f"c_edit_{pid}", use_container_width=True):
                                st.session_state.action_edit_id = None; st.rerun()

                        # --- ΠΡΟΒΟΛΗ ---
                        else:
                            icon = "⚠️" if is_pending else "✅"
                            pc1, pc2, pc3, pc4 = st.columns([3, 2, 2, 3])
                            pc1.write(f"**{icon} {display_type}** | {amt:.2f}€")
                            
                            if is_pending:
                                pc2.write(f"Ημ/νία Έκδοσης: {p_row['Date_Received']}")
                                pc3.write("Κατάσταση: **Εκκρεμεί**")
                            else:
                                pc2.write(f"Ημ/νία Πληρωμής: {p_row['Date_Received']}")
                                pc3.write(f"🏦 {p_row['Bank_Account']}")
                            
                            bc1, bc2, bc3 = pc4.columns(3)
                            if is_pending:
                                if bc1.button("💳 Εξόφληση", key=f"btn_p_{pid}"):
                                    st.session_state.action_pay_id = pid; st.session_state.action_edit_id = None; st.rerun()
                            if bc2.button("✏️ Επεξ.", key=f"btn_e_{pid}"):
                                st.session_state.action_edit_id = pid; st.session_state.action_pay_id = None; st.rerun()
                            if bc3.button("🗑️ Διαγρ.", key=f"btn_d_{pid}"):
                                gsheets_service.delete_payment(pid); st.rerun()

            # --- ΠΡΟΣΘΗΚΗ ΝΕΑΣ ΟΦΕΙΛΗΣ ---
            st.markdown("#### ➕ Προσθήκη Νέας Καταχώρησης")
            with st.form("add_monthly_payment_form"):
                fc1, fc2, fc3 = st.columns([2, 2, 2])
                with fc1: p_type = st.selectbox("Είδος *", ["Ενοίκιο", "Νερό", "Κοινόχρηστα", "Ρεύμα", "Άλλο"])
                with fc2: 
                    rent_paid = pd.to_numeric(p_month_data[p_month_data['Payment_Type'] == 'Ενοίκιο']['Amount'].astype(str).str.replace(',', '.'), errors='coerce').sum() if not p_month_data.empty else 0.0
                    default_amt = str(max(0, expected_rent - rent_paid)).replace('.', ',') if rent_paid < expected_rent else "0"
                    p_amt = st.text_input("Ποσό (€) *", value=default_amt)
                with fc3: p_status = st.radio("Κατάσταση *", ["Εκκρεμεί (Ήρθε λογαριασμός / Χρωστάει)", "Εξοφλήθηκε (Πληρώθηκε)"], index=1)
                
                p_desc = st.text_input("Περιγραφή (προαιρετικό)", placeholder="π.χ. Υδραυλικός, Διαρροή")
                
                hc1, hc2 = st.columns(2)
                with hc1: p_date = st.date_input("Ημερομηνία (Έκδοσης ή Πληρωμής) *", value=date.today())
                with hc2: 
                    is_exof = "Εξοφλήθηκε" in p_status
                    p_bank = st.selectbox("Τράπεζα / Τρόπος", ["Εθνική Τράπεζα", "Eurobank", "Alpha Bank", "Τράπεζα Πειραιώς", "Μετρητά", "Άλλο"]) if is_exof else "Εκκρεμεί"
                
                if st.form_submit_button("Αποθήκευση", use_container_width=True):
                    amt_val = pd.to_numeric(p_amt.replace(',', '.'), errors='coerce')
                    if pd.isna(amt_val): amt_val = 0.0
                    if amt_val > 0:
                        try:
                            clean_status = "Εξοφλήθηκε" if is_exof else "Εκκρεμεί"
                            gsheets_service.add_payment([f"PAY-{uuid.uuid4().hex[:6].upper()}", active_l_id, p_type, p_amt, p_date.strftime("%Y-%m-%d"), p_bank, str(m_idx), str(selected_year), clean_status, p_desc])
                            st.success("Καταχωρήθηκε!")
                            st.rerun() 
                        except Exception as e: st.error(f"Σφάλμα: {e}")
                    else: st.warning("Παρακαλώ εισάγετε έγκυρο ποσό.")

    # =========================================================================
    # --- 2. ΙΣΤΟΡΙΚΟ ---
    # =========================================================================
    with tab_list:
        if payments_df.empty: st.info("Δεν έχουν καταγραφεί εισπράξεις.")
        else:
            pay_list_data = []
            
            l_opts_all = {}
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
                l_opts_all[l_id] = f"{' & '.join(t_names) if t_names else 'Άγνωστος'} | {p_charact}"
                
            for _, row in payments_df.iterrows():
                amt_val = pd.to_numeric(str(row.get('Amount', '0')).replace(',', '.'), errors='coerce')
                if pd.isna(amt_val): amt_val = 0.0
                
                d_text = str(row.get("Description", "")).replace('nan','')
                cat_display = f"{row.get('Payment_Type', '')} ({d_text})" if d_text else row.get("Payment_Type", "")
                
                pay_list_data.append({
                    "Ημερομηνία": row.get("Date_Received", ""),
                    "Μήνας / Έτος": f"{row.get('Calc_Month', '-')} / {row.get('Calc_Year', '-')}",
                    "Μίσθωση / Ενοικιαστής": l_opts_all.get(str(row.get("Lease_ID", "")), "Διαγραμμένη Μίσθωση"),
                    "Είδος": cat_display,
                    "Ποσό": f"{amt_val:.2f} €".replace('.', ','),
                    "Κατάσταση": "✅ Εξοφλήθηκε" if str(row.get("Status", "")) == "Εξοφλήθηκε" else "⚠️ Εκκρεμεί",
                    "Μέθοδος": row.get("Bank_Account", "")
                })
            pay_list_data.reverse()
            st.dataframe(pd.DataFrame(pay_list_data), use_container_width=True, hide_index=True)

    # =========================================================================
    # --- 3. ΕΠΕΞΕΡΓΑΣΙΑ (ΓΕΝΙΚΗ) ---
    # =========================================================================
    with tab_edit:
        if payments_df.empty: st.warning("Δεν υπάρχουν πληρωμές.")
        else:
            p_edit_opts = {str(r.get("Payment_ID", "")): f"{str(r.get('Date_Received', ''))} | {str(r.get('Payment_Type', ''))} {str(r.get('Amount', ''))}€ ({str(r.get('Status', 'Εξοφλήθηκε'))})" for _, r in payments_df.iterrows()}
            selected_pay_edit = st.selectbox("Επιλέξτε Καταχώρηση προς Επεξεργασία", options=list(p_edit_opts.keys()), format_func=lambda x: p_edit_opts[x])
            
            if selected_pay_edit:
                sel_pay = payments_df[payments_df["Payment_ID"] == selected_pay_edit].iloc[0]
                
                l_keys = list(l_opts_all.keys())
                try: l_idx = l_keys.index(str(sel_pay.get("Lease_ID", "")))
                except: l_idx = 0
                try: pay_date = datetime.strptime(str(sel_pay.get("Date_Received", "")), "%Y-%m-%d").date()
                except: pay_date = date.today()

                type_opts, curr_type = ["Ενοίκιο", "Νερό", "Κοινόχρηστα", "Ρεύμα", "Άλλο"], str(sel_pay.get("Payment_Type", ""))
                e_type_global = st.selectbox("Είδος Οφειλής *", type_opts, index=type_opts.index(curr_type) if curr_type in type_opts else 0)

                with st.form("edit_pay_form_global"):
                    e_lease = st.selectbox("Μίσθωση *", options=l_keys, index=l_idx, format_func=lambda x: l_opts_all.get(x, x))
                    
                    ec1, ec2 = st.columns(2)
                    with ec1: e_amount = st.text_input("Ποσό (€) *", value=str(sel_pay.get("Amount", "")).replace('.', ','))
                    curr_status = str(sel_pay.get("Status", "Εξοφλήθηκε"))
                    with ec2: e_status = st.selectbox("Κατάσταση", ["Εκκρεμεί", "Εξοφλήθηκε"], index=0 if curr_status == "Εκκρεμεί" else 1)
                    
                    e_desc_global = st.text_input("Περιγραφή (προαιρετικό)", value=str(sel_pay.get("Description", "")).replace('nan',''))
                    
                    ec4, ec5 = st.columns(2)
                    bank_opts, curr_bank = ["Εθνική Τράπεζα", "Eurobank", "Alpha Bank", "Τράπεζα Πειραιώς", "Μετρητά", "Άλλο"], str(sel_pay.get("Bank_Account", ""))
                    with ec4: e_date_rec = st.date_input("Ημερομηνία *", value=pay_date)
                    with ec5: e_bank = st.selectbox("Τράπεζα / Τρόπος", bank_opts, index=bank_opts.index(curr_bank) if curr_bank in bank_opts else 0)
                    
                    if st.form_submit_button("Αποθήκευση Αλλαγών", type="primary"):
                        amt_val = pd.to_numeric(e_amount.replace(',', '.'), errors='coerce')
                        if pd.isna(amt_val): amt_val = 0.0
                        if e_lease and amt_val > 0:
                            try:
                                gsheets_service.update_payment(selected_pay_edit, [selected_pay_edit, e_lease, e_type_global, e_amount, e_date_rec.strftime("%Y-%m-%d"), e_bank, str(sel_pay.get('For_Month', '')), str(sel_pay.get('For_Year', '')), e_status, e_desc_global])
                                st.success("Οι αλλαγές αποθηκεύτηκαν! Ανανεώστε τη σελίδα.")
                            except Exception as e: st.error(f"Σφάλμα: {e}")
                        else: st.warning("Παρακαλώ εισάγετε έγκυρο ποσό.")
