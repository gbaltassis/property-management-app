import streamlit as st
import gsheets_service
import uuid
import pandas as pd
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
        payments_df = pd.DataFrame(columns=['Payment_ID', 'Lease_ID', 'Payment_Type', 'Amount', 'Date_Received', 'Bank_Account', 'For_Month', 'For_Year', 'Status', 'Calc_Month', 'Calc_Year'])

    # --- SESSION STATE INITIALIZATION ---
    if "payment_modal" not in st.session_state: st.session_state.payment_modal = None
    if "action_pay_id" not in st.session_state: st.session_state.action_pay_id = None
    if "action_edit_id" not in st.session_state: st.session_state.action_edit_id = None

    lease_options = {}
    for _, row in leases_df.iterrows():
        l_id, p_id = str(row.get("Lease_ID", "")), str(row.get("Property_ID", ""))
        if not l_id or l_id == 'nan': continue
        t_names = []
        for tid_clean in [t.strip() for t in str(row.get("Tenant_ID", "")).split(',') if t.strip()]:
            tenants_df['Tenant_ID'] = tenants_df['Tenant_ID'].astype(str)
            t_match = tenants_df[tenants_df["Tenant_ID"] == tid_clean]
            if not t_match.empty: t_names.append(f"{str(t_match.iloc[0].get('Επώνυμο', '')).replace('nan','')} {str(t_match.iloc[0].get('Όνομα', '')).replace('nan','')}")
        prop_address = "Άγνωστο Ακίνητο"
        if not properties_df.empty:
            p_match = properties_df[properties_df["Property_ID"] == p_id]
            if not p_match.empty: prop_address = f"{str(p_match.iloc[0].get('Χαρακτηριστικό', '')).replace('nan', '')}"
        lease_options[l_id] = f"{' & '.join(t_names) if t_names else 'Άγνωστος'} | {prop_address}"

    tab_matrix, tab_list = st.tabs(["📊 Πίνακας Ελέγχου", "📋 Ιστορικό Όλων των Εισπράξεων"])

    # =========================================================================
    # --- 1. MATRIX (ΕΤΗΣΙΑ ΕΠΙΣΚΟΠΗΣΗ ΜΕ ΠΟΛΛΑΠΛΑ ΚΟΥΤΙΑ) ---
    # =========================================================================
    with tab_matrix:
        current_year = datetime.today().year
        selected_year = st.selectbox("Επιλογή Έτους", [current_year - 1, current_year, current_year + 1, current_year + 2], index=1)
        st.subheader(f"Κατάσταση Μισθωμάτων & Λογαριασμών - {selected_year}")

        months = ["Ιαν", "Φεβ", "Μαρ", "Απρ", "Μάι", "Ιουν", "Ιουλ", "Αυγ", "Σεπ", "Οκτ", "Νοε", "Δεκ"]
        cols = st.columns([3] + [1]*12)
        cols[0].markdown("**Ακίνητο & Ενοικιαστής**")
        for i, m_name in enumerate(months): cols[i+1].markdown(f"**{m_name}**")

        for _, lease in leases_df.iterrows():
            l_id, p_id = str(lease.get("Lease_ID", "")), str(lease.get("Property_ID", ""))
            
            prop_charact = "-"
            if not properties_df.empty:
                p_match = properties_df[properties_df["Property_ID"] == p_id]
                if not p_match.empty: prop_charact = str(p_match.iloc[0].get('Χαρακτηριστικό', '-'))
                    
            tenant_name = lease_options.get(l_id, "").split(" | ")[0]
            expected_rent = pd.to_numeric(str(lease.get('Monthly_Rent', '0')).replace(',', '.'), errors='coerce')
            if pd.isna(expected_rent): expected_rent = 0.0

            row_cols = st.columns([3] + [1]*12)
            row_cols[0].write(f"🏠 {prop_charact}\n👤 {tenant_name}")

            for m_idx in range(1, 13):
                with row_cols[m_idx]:
                    p_month = payments_df[(payments_df['Lease_ID'] == l_id) & (payments_df['Calc_Month'] == str(m_idx)) & (payments_df['Calc_Year'] == str(selected_year))]
                    
                    if p_month.empty:
                        # Μήνας Κενός -> Εμφάνιση ενός κουμπιού
                        if st.button("❌ Κενό", key=f"btn_{l_id}_{m_idx}_{selected_year}_empty", use_container_width=True):
                            st.session_state.payment_modal = {"lease_id": l_id, "month": m_idx, "year": selected_year, "prop_charact": prop_charact, "tenant_name": tenant_name, "expected_rent": expected_rent}
                            st.session_state.action_pay_id = None
                            st.session_state.action_edit_id = None
                            st.rerun()
                    else:
                        # Μήνας με δεδομένα -> Στοίβαξη κουμπιών για κάθε ξεχωριστό "Είδος"
                        for p_type in p_month['Payment_Type'].unique():
                            type_data = p_month[p_month['Payment_Type'] == p_type]
                            is_pending = not type_data[type_data['Status'] == 'Εκκρεμεί'].empty
                            
                            if p_type == 'Ενοίκιο':
                                rent_paid_amt = pd.to_numeric(type_data[type_data['Status'] == 'Εξοφλήθηκε']['Amount'].astype(str).str.replace(',', '.'), errors='coerce').sum()
                                if is_pending:
                                    btn_text = f"\n⚠️Ενοίκιο Εκκρεμεί"
                                elif rent_paid_amt < expected_rent:
                                    btn_text = f"Ενοίκιο\n⚠️ {rent_paid_amt:.0f}€"
                                else:
                                    btn_text = f"\n✅Ενοίκιο Εξοφλ."
                            else:
                                # Για άλλους λογαριασμούς (Νερό, Ρεύμα)
                                short_type = p_type[:6] + "." if len(p_type) > 8 else p_type
                                if is_pending:
                                    btn_text = f"{short_type}\n⚠️ Εκκρεμεί"
                                else:
                                    btn_text = f"\n✅{short_type} Εξοφλ."
                                    
                            if st.button(btn_text, key=f"btn_{l_id}_{m_idx}_{selected_year}_{p_type}", use_container_width=True):
                                st.session_state.payment_modal = {"lease_id": l_id, "month": m_idx, "year": selected_year, "prop_charact": prop_charact, "tenant_name": tenant_name, "expected_rent": expected_rent}
                                st.session_state.action_pay_id = None
                                st.session_state.action_edit_id = None
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
                    st.session_state.action_pay_id = None
                    st.session_state.action_edit_id = None
                    st.rerun()

            p_month_data = payments_df[(payments_df['Lease_ID'] == m_info['lease_id']) & (payments_df['Calc_Month'] == str(m_info['month'])) & (payments_df['Calc_Year'] == str(m_info['year']))]
            
            # --- 1. ΛΙΣΤΑ ΥΠΑΡΧΟΝΤΩΝ ΕΓΓΡΑΦΩΝ ΜΕ INLINE ΕΠΕΞΕΡΓΑΣΙΑ ---
            st.markdown("#### 📋 Καταχωρημένες Οφειλές & Εισπράξεις")
            if p_month_data.empty: 
                st.info("Δεν υπάρχει καμία καταχώρηση για αυτόν τον μήνα.")
            else:
                for _, p_row in p_month_data.iterrows():
                    pid = p_row['Payment_ID']
                    amt = pd.to_numeric(str(p_row['Amount']).replace(',', '.'), errors='coerce')
                    if pd.isna(amt): amt = 0.0
                    is_pending = (str(p_row.get('Status', '')) == 'Εκκρεμεί')
                    
                    with st.container(border=True):
                        # --- SCENARIO A: ΠΑΤΗΘΗΚΕ ΤΟ ΚΟΥΜΠΙ "ΕΞΟΦΛΗΣΗ" ---
                        if st.session_state.action_pay_id == pid:
                            st.write(f"💳 **Ολοκλήρωση Πληρωμής:** {p_row['Payment_Type']} | {amt:.2f}€")
                            pay_c1, pay_c2, pay_c3, pay_c4 = st.columns([2, 2, 1, 1])
                            pay_date = pay_c1.date_input("Ημ/νία Εξόφλησης", value=date.today(), key=f"d_pay_{pid}")
                            pay_bank = pay_c2.selectbox("Τράπεζα / Τρόπος", ["Εθνική Τράπεζα", "Eurobank", "Alpha Bank", "Τράπεζα Πειραιώς", "Μετρητά", "Άλλο"], key=f"b_pay_{pid}")
                            
                            st.write("") 
                            if pay_c3.button("💾 Αποθήκευση", key=f"s_pay_{pid}", type="primary", use_container_width=True):
                                try:
                                    new_row = [pid, p_row['Lease_ID'], p_row['Payment_Type'], p_row['Amount'], pay_date.strftime("%Y-%m-%d"), pay_bank, p_row['For_Month'], p_row['For_Year'], "Εξοφλήθηκε"]
                                    gsheets_service.update_payment(pid, new_row)
                                    st.session_state.action_pay_id = None
                                    st.rerun()
                                except Exception as e: st.error(f"Σφάλμα: {e}")
                                
                            if pay_c4.button("Άκυρο", key=f"c_pay_{pid}", use_container_width=True):
                                st.session_state.action_pay_id = None
                                st.rerun()
                        
                        # --- SCENARIO B: ΠΑΤΗΘΗΚΕ ΤΟ ΚΟΥΜΠΙ "ΕΠΕΞΕΡΓΑΣΙΑ" ---
                        elif st.session_state.action_edit_id == pid:
                            st.write(f"✏️ **Επεξεργασία Εγγραφής**")
                            e_c1, e_c2, e_c3 = st.columns(3)
                            
                            type_opts = ["Ενοίκιο", "Νερό", "Κοινόχρηστα", "Ρεύμα", "Άλλο"]
                            e_type = e_c1.selectbox("Είδος", type_opts, index=type_opts.index(p_row['Payment_Type']) if p_row['Payment_Type'] in type_opts else 0, key=f"et_{pid}")
                            e_amt = e_c2.text_input("Ποσό (€)", value=str(p_row['Amount']).replace('.', ','), key=f"ea_{pid}")
                            e_status = e_c3.selectbox("Κατάσταση", ["Εκκρεμεί", "Εξοφλήθηκε"], index=0 if is_pending else 1, key=f"es_{pid}")
                            
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
                                    new_row = [pid, p_row['Lease_ID'], e_type, e_amt, e_date.strftime("%Y-%m-%d"), final_bank, p_row['For_Month'], p_row['For_Year'], e_status]
                                    gsheets_service.update_payment(pid, new_row)
                                    st.session_state.action_edit_id = None
                                    st.rerun()
                                except Exception as e: st.error(f"Σφάλμα: {e}")
                                
                            if e_c7.button("Άκυρο", key=f"c_edit_{pid}", use_container_width=True):
                                st.session_state.action_edit_id = None
                                st.rerun()

                        # --- SCENARIO C: ΚΑΝΟΝΙΚΗ ΠΡΟΒΟΛΗ ---
                        else:
                            icon = "⚠️" if is_pending else "✅"
                            pc1, pc2, pc3, pc4 = st.columns([3, 2, 2, 3])
                            pc1.write(f"**{icon} {p_row['Payment_Type']}** | {amt:.2f}€")
                            
                            if is_pending:
                                pc2.write(f"Ημ/νία Έκδοσης: {p_row['Date_Received']}")
                                pc3.write("Κατάσταση: **Εκκρεμεί**")
                            else:
                                pc2.write(f"Ημ/νία Πληρωμής: {p_row['Date_Received']}")
                                pc3.write(f"🏦 {p_row['Bank_Account']}")
                            
                            bc1, bc2, bc3 = pc4.columns(3)
                            if is_pending:
                                if bc1.button("💳 Εξόφληση", key=f"btn_p_{pid}", help="Πληρωμή τώρα"):
                                    st.session_state.action_pay_id = pid
                                    st.session_state.action_edit_id = None
                                    st.rerun()
                            if bc2.button("✏️ Επεξ.", key=f"btn_e_{pid}", help="Επεξεργασία"):
                                st.session_state.action_edit_id = pid
                                st.session_state.action_pay_id = None
                                st.rerun()
                            if bc3.button("🗑️ Διαγρ.", key=f"btn_d_{pid}", help="Διαγραφή"):
                                gsheets_service.delete_payment(pid)
                                st.rerun()

            # --- 2. ΠΡΟΣΘΗΚΗ ΝΕΑΣ ΟΦΕΙΛΗΣ/ΕΙΣΠΡΑΞΗΣ ---
            st.markdown("#### ➕ Προσθήκη Νέας Καταχώρησης (για αυτόν τον μήνα)")
            with st.form("add_monthly_payment_form"):
                fc1, fc2, fc3 = st.columns([2, 2, 2])
                with fc1: p_type = st.selectbox("Είδος *", ["Ενοίκιο", "Νερό", "Κοινόχρηστα", "Ρεύμα", "Άλλο"])
                with fc2: 
                    rent_paid = pd.to_numeric(p_month_data[p_month_data['Payment_Type'] == 'Ενοίκιο']['Amount'].astype(str).str.replace(',', '.'), errors='coerce').sum() if not p_month_data.empty else 0.0
                    default_amt = str(max(0, m_info['expected_rent'] - rent_paid)).replace('.', ',') if rent_paid < m_info['expected_rent'] else "0"
                    p_amt = st.text_input("Ποσό (€) *", value=default_amt if p_type == "Ενοίκιο" else "0")
                with fc3: p_status = st.radio("Κατάσταση *", ["Εκκρεμεί (Ήρθε λογαριασμός / Χρωστάει)", "Εξοφλήθηκε (Πληρώθηκε)"], index=1)
                
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
                            gsheets_service.add_payment([f"PAY-{uuid.uuid4().hex[:6].upper()}", m_info['lease_id'], p_type, p_amt, p_date.strftime("%Y-%m-%d"), p_bank, str(m_info['month']), str(m_info['year']), clean_status])
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
                pay_list_data.append({
                    "Ημερομηνία": row.get("Date_Received", ""),
                    "Μήνας / Έτος": f"{row.get('Calc_Month', '-')} / {row.get('Calc_Year', '-')}",
                    "Μίσθωση / Ενοικιαστής": lease_options.get(str(row.get("Lease_ID", "")), "Διαγραμμένη Μίσθωση"),
                    "Είδος": row.get("Payment_Type", ""),
                    "Ποσό": f"{amt_val:.2f} €".replace('.', ','),
                    "Κατάσταση": "✅ Εξοφλήθηκε" if str(row.get("Status", "")) == "Εξοφλήθηκε" else "⚠️ Εκκρεμεί",
                    "Μέθοδος": row.get("Bank_Account", "")
                })
            pay_list_data.reverse()
            st.dataframe(pd.DataFrame(pay_list_data), use_container_width=True, hide_index=True)
