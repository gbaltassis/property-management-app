import streamlit as st
import gsheets_service
import uuid
import pandas as pd
from datetime import date, datetime

COMMON_CSS = """
<style>
    /* ΕΞΑΝΑΓΚΑΣΜΟΣ ΟΡΙΖΟΝΤΙΑΣ ΚΥΛΙΣΗΣ ΓΙΑ ΤΟ MATRIX ΣΤΟ ΚΙΝΗΤΟ */
    [data-testid="stHorizontalBlock"]:has(> [data-testid="column"]:nth-child(13)) {
        flex-wrap: nowrap !important;
        overflow-x: auto !important;
        padding-bottom: 10px;
    }
    /* Ελάχιστο πλάτος για τους μήνες ώστε να μη συμπιέζονται */
    [data-testid="stHorizontalBlock"]:has(> [data-testid="column"]:nth-child(13)) > [data-testid="column"] {
        min-width: 120px !important;
    }
    /* ΠΑΓΩΜΑ ΤΗΣ ΠΡΩΤΗΣ ΣΤΗΛΗΣ (Ακίνητο & Ενοικιαστής) */
    [data-testid="stHorizontalBlock"]:has(> [data-testid="column"]:nth-child(13)) > [data-testid="column"]:first-child {
        min-width: 250px !important;
        position: sticky;
        left: 0;
        background-color: #ffffff;
        z-index: 10;
        border-right: 2px solid #f0f2f6;
        padding-right: 10px;
    }
    /* Dark Mode υποστήριξη για την παγωμένη στήλη */
    @media (prefers-color-scheme: dark) {
        [data-testid="stHorizontalBlock"]:has(> [data-testid="column"]:nth-child(13)) > [data-testid="column"]:first-child {
            background-color: #0e1117;
            border-right: 2px solid #262730;
        }
    }
</style>
"""

def show():
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

    tab_matrix, tab_list, tab_edit = st.tabs(["📊 Πίνακας Ελέγχου", "📋 Ιστορικό Όλων των Εισπράξεων", "✏️ Επεξεργασία"])

    # =========================================================================
    # --- 1. MATRIX (ΕΤΗΣΙΑ ΕΠΙΣΚΟΠΗΣΗ) ---
    # =========================================================================
    with tab_matrix:
        current_year = datetime.today().year
        selected_year = st.selectbox("Επιλογή Έτους", [current_year - 1, current_year, current_year + 1, current_year + 2], index=1)
        st.subheader(f"Κατάσταση Μισθωμάτων & Λογαριασμών - {selected_year}")

        months = ["Ιαν", "Φεβ", "Μαρ", "Απρ", "Μάι", "Ιουν", "Ιουλ", "Αυγ", "Σεπ", "Οκτ", "Νοε", "Δεκ"]
        cols = st.columns([3] + [1]*12)
        cols[0].markdown("**Ακίνητο & Ενοικιαστής**")
        for i, m_name in enumerate(months): cols[i+1].markdown(f"**{m_name}**")

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

            row_cols = st.columns([3] + [1]*12)
            row_cols[0].write(f"🏠 {prop_charact}\n👤 {tenant_name}")

            for m_idx in range(1, 13):
                with row_cols[m_idx]:
                    expected_rent, active_l_id = get_expected_rent_and_lease(group_leases, selected_year, m_idx)
                    p_month = payments_df[(payments_df['Lease_ID'].isin(l_id_list)) & (payments_df['Calc_Month'] == str(m_idx)) & (payments_df['Calc_Year'] == str(selected_year))]
                    
                    if p_month.empty:
                        if st.button("❌ Κενό", key=f"btn_{active_l_id}_{m_idx}_{selected_year}_empty", use_container_width=True):
                            st.session_state.payment_modal = {"lease_id_list": l_id_list, "active_lease_id": active_l_id, "month": m_idx, "year": selected_year, "prop_charact": prop_charact, "tenant_name": tenant_name, "expected_rent": expected_rent}
                            st.session_state.action_pay_id = None; st.session_state.action_edit_id = None
                            st.rerun()
                    else:
                        for p_type in p_month['Payment_Type'].unique():
                            type_data = p_month[p_month['Payment_Type'] == p_type]
                            is_pending = not type_data[type_data['Status'] == 'Εκκρεμεί'].empty
                            
                            if p_type == 'Ενοίκιο':
                                rent_paid_amt = pd.to_numeric(type_data[type_data['Status'] == 'Εξοφλήθηκε']['Amount'].astype(str).str.replace(',', '.'), errors='coerce').sum()
                                if is_pending: btn_text = f"\n⚠️Ενοίκιο Εκκρεμεί"
                                elif rent_paid_amt < expected_rent: btn_text = f"\n⚠️Ενοίκιο {rent_paid_amt:.0f}€"
                                else: btn_text = f"\n✅Ενοίκιο Εξοφλ."
                            else:
                                short_type = p_type[:6] + "." if len(p_type) > 8 else p_type
                                btn_text = f"\n⚠️{short_type} Εκκρεμεί" if is_pending else f"\n✅{short_type} Εξοφλ."
                                    
                            if st.button(btn_text, key=f"btn_{active_l_id}_{m_idx}_{selected_year}_{p_type}", use_container_width=True):
                                st.session_state.payment_modal = {"lease_id_list": l_id_list, "active_lease_id": active_l_id, "month": m_idx, "year": selected_year, "prop_charact": prop_charact, "tenant_name": tenant_name, "expected_rent": expected_rent}
                                st.session_state.action_pay_id = None; st.session_state.action_edit_id = None
                                st.rerun()

        # ==========================================
        # --- ΠΑΡΑΘΥΡΟ ΔΙΑΧΕΙΡΙΣΗΣ ΜΗΝΑ (MODAL) ---
        # ==========================================
        if st.session_state.payment_modal:
            m_info = st.session_state.payment_modal
            st.markdown("---")
            
            col_t, col_b = st.columns([4, 1])
            with col_t:
                st.markdown(f"### ⚙️ Διαχείριση Μήνα: **{months[m_info['month']-1]} {m_info['year']}**")
                st.caption(f"🏠 {m_info['prop_charact']} | 👤 {m_info['tenant_name']}")
            with col_b:
                if st.button("❌ Κλείσιμο", use_container_width=True):
                    st.session_state.payment_modal = None
                    st.rerun()

            p_month_data = payments_df[(payments_df['Lease_ID'].isin(m_info['lease_id_list'])) & (payments_df['Calc_Month'] == str(m_info['month'])) & (payments_df['Calc_Year'] == str(m_info['year']))]
            
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
                            
                            e_desc = st.text_input("Περιγραφή *", value=desc_text, key=f"edesc_{pid}") if e_type == "Άλλο" else ""
                            
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
            st.markdown("#### ➕ Προσθήκη Νέας Καταχώρησης (για αυτόν τον μήνα)")
            
            p_type = st.selectbox("Είδος *", ["Ενοίκιο", "Νερό", "Κοινόχρηστα", "Ρεύμα", "Άλλο"], key="modal_new_type")
            
            with st.form("add_monthly_payment_form"):
                p_desc = st.text_input("Περιγραφή *", placeholder="π.χ. Υδραυλικός, Διαρροή") if p_type == "Άλλο" else ""
                
                fc1, fc2 = st.columns(2)
                with fc1: 
                    rent_paid = pd.to_numeric(p_month_data[p_month_data['Payment_Type'] == 'Ενοίκιο']['Amount'].astype(str).str.replace(',', '.'), errors='coerce').sum() if not p_month_data.empty else 0.0
                    default_amt = str(max(0, m_info['expected_rent'] - rent_paid)).replace('.', ',') if rent_paid < m_info['expected_rent'] else "0"
                    p_amt = st.text_input("Ποσό (€) *", value=default_amt if p_type == "Ενοίκιο" else "0")
                with fc2: p_status = st.radio("Κατάσταση *", ["Εκκρεμεί (Ήρθε λογαριασμός / Χρωστάει)", "Εξοφλήθηκε (Πληρώθηκε)"], index=1)
                
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
                            gsheets_service.add_payment([f"PAY-{uuid.uuid4().hex[:6].upper()}", m_info['active_lease_id'], p_type, p_amt, p_date.strftime("%Y-%m-%d"), p_bank, str(m_info['month']), str(m_info['year']), clean_status, p_desc])
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
            for _, row in payments_df.iterrows():
                amt_val = pd.to_numeric(str(row.get('Amount', '0')).replace(',', '.'), errors='coerce')
                if pd.isna(amt_val): amt_val = 0.0
                
                d_text = str(row.get("Description", "")).replace('nan','')
                cat_display = f"{row.get('Payment_Type', '')} ({d_text})" if d_text and row.get('Payment_Type') == 'Άλλο' else row.get("Payment_Type", "")
                
                l_id = str(row.get("Lease_ID", ""))
                l_match = leases_df[leases_df["Lease_ID"] == l_id] if not leases_df.empty else pd.DataFrame()
                p_charact = "-"
                t_name = "-"
                if not l_match.empty:
                    p_id = str(l_match.iloc[0].get("Property_ID", ""))
                    p_match = properties_df[properties_df["Property_ID"] == p_id] if not properties_df.empty else pd.DataFrame()
                    if not p_match.empty: p_charact = str(p_match.iloc[0].get('Χαρακτηριστικό', '-'))
                    
                    t_names = []
                    for tid_clean in [t.strip() for t in str(l_match.iloc[0].get("Tenant_ID", "")).split(',') if t.strip()]:
                        t_match = tenants_df[tenants_df["Tenant_ID"] == tid_clean]
                        if not t_match.empty: t_names.append(f"{str(t_match.iloc[0].get('Επώνυμο', ''))} {str(t_match.iloc[0].get('Όνομα', ''))}")
                    t_name = " & ".join(t_names) if t_names else "Άγνωστος"
                
                pay_list_data.append({
                    "Ημερομηνία": row.get("Date_Received", ""),
                    "Μήνας / Έτος": f"{row.get('Calc_Month', '-')} / {row.get('Calc_Year', '-')}",
                    "Μίσθωση / Ενοικιαστής": f"{t_name} | {p_charact}",
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
                    
                    e_desc_global = st.text_input("Περιγραφή *", value=str(sel_pay.get("Description", "")).replace('nan','')) if e_type_global == "Άλλο" else ""
                    
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
