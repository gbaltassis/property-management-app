import streamlit as st
import gsheets_service
import uuid
import pandas as pd
from datetime import date, datetime

def show():
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
        if "Status" not in payments_df.columns: payments_df["Status"] = "Εξοφλήθηκε" # Προεπιλογή για παλιά δεδομένα
        
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
        
        # Καθαρισμός Status: Αν είναι κενό (NaN) στις παλιές εγγραφές, να γίνει "Εξοφλήθηκε"
        payments_df['Status'] = payments_df['Status'].fillna('Εξοφλήθηκε')
        payments_df['Status'] = payments_df['Status'].replace('', 'Εξοφλήθηκε')
    else:
        payments_df = pd.DataFrame(columns=['Payment_ID', 'Lease_ID', 'Payment_Type', 'Amount', 'Date_Received', 'Bank_Account', 'For_Month', 'For_Year', 'Status', 'Calc_Month', 'Calc_Year'])

    if "payment_modal" not in st.session_state: st.session_state.payment_modal = None

    # --- ΠΡΟΕΤΟΙΜΑΣΙΑ ΛΙΣΤΑΣ ΜΙΣΘΩΣΕΩΝ ---
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

    tab_matrix, tab_list, tab_edit = st.tabs(["📊 Πίνακας Ελέγχου", "📋 Ιστορικό", "✏️ Επεξεργασία"])

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
                # Φιλτράρουμε όλες τις καταχωρήσεις για αυτόν τον μήνα
                p_month = payments_df[(payments_df['Lease_ID'] == l_id) & (payments_df['Calc_Month'] == str(m_idx)) & (payments_df['Calc_Year'] == str(selected_year))]
                
                # Ελέγχουμε αν υπάρχει έστω και ΜΙΑ οφειλή που εκκρεμεί (Ενοίκιο ή Λογαριασμός)
                has_pending = False
                has_rent_recorded = False
                rent_paid_amt = 0.0
                
                if not p_month.empty:
                    pending_records = p_month[p_month['Status'] == 'Εκκρεμεί']
                    if not pending_records.empty: has_pending = True
                    
                    # Βλέπουμε τι γίνεται με το ενοίκιο
                    rent_records = p_month[p_month['Payment_Type'] == 'Ενοίκιο']
                    if not rent_records.empty:
                        has_rent_recorded = True
                        # Υπολογίζουμε μόνο τα "Εξοφλημένα" ενοίκια
                        rent_paid_amt = pd.to_numeric(rent_records[rent_records['Status'] == 'Εξοφλήθηκε']['Amount'].astype(str).str.replace(',', '.'), errors='coerce').sum()

                # --- ΛΟΓΙΚΗ ΕΜΦΑΝΙΣΗΣ ΚΟΥΜΠΙΟΥ ---
                if p_month.empty:
                    # Τίποτα δεν έχει καταχωρηθεί (Μήνας κενός)
                    status_icon = "❌ Κενό"
                elif has_pending:
                    # Υπάρχει καταχωρημένη οφειλή που περιμένει πληρωμή (είτε ενοίκιο είτε νερό)
                    status_icon = "⚠️ Εκκρεμεί"
                elif has_rent_recorded and rent_paid_amt < expected_rent:
                    # Καταχωρήθηκε ενοίκιο ως "Εξοφλημένο" αλλά τα χρήματα είναι λιγότερα
                    status_icon = f"⚠️ {rent_paid_amt:.0f}€"
                else:
                    # Όλα όσα έχουν καταχωρηθεί (ενοίκια και λογαριασμοί) είναι "Εξοφλήθηκε"
                    status_icon = "✅ Εξοφλήθη"
                    
                if row_cols[m_idx].button(status_icon, key=f"btn_{l_id}_{m_idx}_{selected_year}", use_container_width=True):
                    st.session_state.payment_modal = {
                        "lease_id": l_id, "month": m_idx, "year": selected_year,
                        "prop_charact": prop_charact, "tenant_name": tenant_name,
                        "expected_rent": expected_rent
                    }
                    st.rerun()

        # ==========================================
        # --- ΠΑΡΑΘΥΡΟ ΔΙΑΧΕΙΡΙΣΗΣ ΜΗΝΑ ---
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

            p_month_data = payments_df[(payments_df['Lease_ID'] == m_info['lease_id']) & (payments_df['Calc_Month'] == str(m_info['month'])) & (payments_df['Calc_Year'] == str(m_info['year']))]
            
            # --- Υπάρχουσες Οφειλές / Εισπράξεις ---
            st.markdown("#### 📋 Καταχωρημένες Οφειλές & Εισπράξεις")
            if p_month_data.empty: 
                st.info("Δεν υπάρχει καμία καταχώρηση για αυτόν τον μήνα.")
            else:
                for _, p_row in p_month_data.iterrows():
                    amt = pd.to_numeric(str(p_row['Amount']).replace(',', '.'), errors='coerce')
                    if pd.isna(amt): amt = 0.0
                    
                    is_pending = (str(p_row.get('Status', '')) == 'Εκκρεμεί')
                    box_color = "warning" if is_pending else "success"
                    icon = "⚠️" if is_pending else "✅"
                    
                    with st.container():
                        pc1, pc2, pc3, pc4 = st.columns([3, 2, 2, 2])
                        pc1.write(f"**{icon} {p_row['Payment_Type']}** | {amt:.2f}€")
                        
                        if is_pending:
                            pc2.write(f"Ημ/νία Έκδοσης: {p_row['Date_Received']}")
                            pc3.write("Κατάσταση: **Εκκρεμεί**")
                            # Αν εκκρεμεί, δείχνουμε κουμπί για άμεση "Εξόφληση"
                            if pc4.button("💳 Εξόφληση", key=f"exof_{p_row['Payment_ID']}", use_container_width=True):
                                try:
                                    # Κρατάμε τα ίδια στοιχεία, αλλάζουμε μόνο το Status και βάζουμε σημερινή ημερομηνία
                                    new_row = [p_row['Payment_ID'], p_row['Lease_ID'], p_row['Payment_Type'], str(p_row['Amount']), date.today().strftime("%Y-%m-%d"), "Μετρητά/Άλλο", str(m_info['month']), str(m_info['year']), "Εξοφλήθηκε"]
                                    gsheets_service.update_payment(p_row['Payment_ID'], new_row)
                                    st.success("Μαρκαρίστηκε ως Εξοφλημένο!")
                                    st.rerun()
                                except Exception as e: st.error(f"Σφάλμα: {e}")
                        else:
                            pc2.write(f"Ημ/νία Πληρωμής: {p_row['Date_Received']}")
                            pc3.write(f"🏦 {p_row['Bank_Account']}")
                            if pc4.button("🗑️ Διαγραφή", key=f"del_{p_row['Payment_ID']}", use_container_width=True):
                                try:
                                    gsheets_service.delete_payment(p_row['Payment_ID'])
                                    st.rerun()
                                except Exception as e: st.error(f"Σφάλμα: {e}")
                        st.markdown("---")

            # --- Προσθήκη Νέας Οφειλής/Είσπραξης ---
            st.markdown("#### ➕ Προσθήκη Νέας Καταχώρησης")
            with st.form("add_monthly_payment_form"):
                fc1, fc2, fc3 = st.columns([2, 2, 2])
                with fc1: p_type = st.selectbox("Είδος *", ["Ενοίκιο", "Νερό", "Κοινόχρηστα", "Ρεύμα", "Άλλο"])
                with fc2: p_amt = st.text_input("Ποσό (€) *", value=str(m_info['expected_rent']).replace('.', ',') if p_type == "Ενοίκιο" else "0")
                with fc3: p_status = st.radio("Κατάσταση *", ["Εκκρεμεί (Ήρθε λογαριασμός / Χρωστάει)", "Εξοφλήθηκε (Πληρώθηκε)"], index=1)
                
                hc1, hc2 = st.columns(2)
                with hc1: p_date = st.date_input("Ημερομηνία (Έκδοσης ή Πληρωμής) *", value=date.today())
                with hc2: 
                    # Αν εκκρεμεί, δεν έχει νόημα η τράπεζα
                    is_exof = "Εξοφλήθηκε" in p_status
                    p_bank = st.selectbox("Τράπεζα / Τρόπος", ["Εθνική Τράπεζα", "Eurobank", "Alpha Bank", "Τράπεζα Πειραιώς", "Μετρητά", "Άλλο"]) if is_exof else "Εκκρεμεί"
                
                if st.form_submit_button("Αποθήκευση", use_container_width=True):
                    amt_val = pd.to_numeric(p_amt.replace(',', '.'), errors='coerce')
                    if pd.isna(amt_val): amt_val = 0.0
                    if amt_val > 0:
                        try:
                            clean_status = "Εξοφλήθηκε" if is_exof else "Εκκρεμεί"
                            # ΠΡΟΣΟΧΗ: Το Status είναι το 9ο στοιχείο τώρα (index 8)
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
                    "Κατάσταση": "✅ Εξοφλήθηκε" if str(row.get("Status", "")) == "Εξοφλήθηκε" else "⚠️ Εκκρεμεί"
                })
            pay_list_data.reverse()
            st.dataframe(pd.DataFrame(pay_list_data), use_container_width=True, hide_index=True)

    # =========================================================================
    # --- 3. ΕΠΕΞΕΡΓΑΣΙΑ ΠΛΗΡΩΜΗΣ ---
    # =========================================================================
    with tab_edit:
        if payments_df.empty: st.warning("Δεν υπάρχουν πληρωμές.")
        else:
            p_edit_opts = {str(r.get("Payment_ID", "")): f"{str(r.get('Date_Received', ''))} | {str(r.get('Payment_Type', ''))} {str(r.get('Amount', ''))}€ ({str(r.get('Status', 'Εξοφλήθηκε'))})" for _, r in payments_df.iterrows()}
            selected_pay_edit = st.selectbox("Επιλέξτε Καταχώρηση προς Επεξεργασία", options=list(p_edit_opts.keys()), format_func=lambda x: p_edit_opts[x])
            
            if selected_pay_edit:
                sel_pay = payments_df[payments_df["Payment_ID"] == selected_pay_edit].iloc[0]
                l_keys = list(lease_options.keys())
                try: l_idx = l_keys.index(str(sel_pay.get("Lease_ID", "")))
                except: l_idx = 0
                try: pay_date = datetime.strptime(str(sel_pay.get("Date_Received", "")), "%Y-%m-%d").date()
                except: pay_date = date.today()

                with st.form("edit_pay_form"):
                    e_lease = st.selectbox("Μίσθωση *", options=l_keys, index=l_idx, format_func=lambda x: lease_options.get(x, x))
                    
                    ec1, ec2, ec3 = st.columns([2, 2, 2])
                    type_opts, curr_type = ["Ενοίκιο", "Νερό", "Κοινόχρηστα", "Ρεύμα", "Άλλο"], str(sel_pay.get("Payment_Type", ""))
                    with ec1: e_type = st.selectbox("Είδος Οφειλής *", type_opts, index=type_opts.index(curr_type) if curr_type in type_opts else 0)
                    with ec2: e_amount = st.text_input("Ποσό (€) *", value=str(sel_pay.get("Amount", "")).replace('.', ','))
                    curr_status = str(sel_pay.get("Status", "Εξοφλήθηκε"))
                    with ec3: e_status = st.selectbox("Κατάσταση", ["Εκκρεμεί", "Εξοφλήθηκε"], index=0 if curr_status == "Εκκρεμεί" else 1)
                    
                    ec4, ec5 = st.columns(2)
                    bank_opts, curr_bank = ["Εθνική Τράπεζα", "Eurobank", "Alpha Bank", "Τράπεζα Πειραιώς", "Μετρητά", "Άλλο"], str(sel_pay.get("Bank_Account", ""))
                    with ec4: e_date_rec = st.date_input("Ημερομηνία *", value=pay_date)
                    with ec5: e_bank = st.selectbox("Τράπεζα / Τρόπος", bank_opts, index=bank_opts.index(curr_bank) if curr_bank in bank_opts else 0)
                    
                    if st.form_submit_button("Αποθήκευση Αλλαγών", type="primary"):
                        amt_val = pd.to_numeric(e_amount.replace(',', '.'), errors='coerce')
                        if pd.isna(amt_val): amt_val = 0.0
                        if e_lease and amt_val > 0:
                            try:
                                gsheets_service.update_payment(selected_pay_edit, [selected_pay_edit, e_lease, e_type, e_amount, e_date_rec.strftime("%Y-%m-%d"), e_bank, str(sel_pay.get('For_Month', '')), str(sel_pay.get('For_Year', '')), e_status])
                                st.success("Οι αλλαγές αποθηκεύτηκαν! Ανανεώστε τη σελίδα.")
                            except Exception as e: st.error(f"Σφάλμα: {e}")
                        else: st.warning("Παρακαλώ εισάγετε έγκυρο ποσό.")
