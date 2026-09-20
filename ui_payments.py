import streamlit as st
import gsheets_service
import uuid
import pandas as pd
from datetime import date, datetime

def show():
    st.header("Καταγραφή & Παρακολούθηση Πληρωμών")
    
    try:
        leases_df = gsheets_service.fetch_all_leases()
        tenants_df = gsheets_service.fetch_all_tenants()
        properties_df = gsheets_service.fetch_all_properties()
        payments_df = gsheets_service.fetch_all_payments()
    except Exception as e:
        st.error(f"Αδυναμία φόρτωσης δεδομένων: {e}")
        return

    # Προετοιμασία Λίστας Επιλογών (για τα Dropdowns των φορμών)
    lease_options = {}
    if not leases_df.empty:
        for _, row in leases_df.iterrows():
            l_id, p_id = str(row.get("Lease_ID", "")), str(row.get("Property_ID", ""))
            if not l_id or l_id == 'nan': continue
                
            t_names = []
            for tid_clean in [t.strip() for t in str(row.get("Tenant_ID", "")).split(',') if t.strip()]:
                tenants_df['Tenant_ID'] = tenants_df['Tenant_ID'].astype(str)
                t_match = tenants_df[tenants_df["Tenant_ID"] == tid_clean]
                if not t_match.empty: t_names.append(f"{str(t_match.iloc[0].get('Όνομα', '')).replace('nan','')} {str(t_match.iloc[0].get('Επώνυμο', '')).replace('nan','')}")
            
            prop_address = "Άγνωστο Ακίνητο"
            if not properties_df.empty and "Property_ID" in properties_df.columns:
                properties_df['Property_ID'] = properties_df['Property_ID'].astype(str)
                p_match = properties_df[properties_df["Property_ID"] == p_id]
                if not p_match.empty: prop_address = f"{str(p_match.iloc[0].get('Χαρακτηριστικό', '')).replace('nan', '')} ({str(p_match.iloc[0].get('Διεύθυνση', '')).replace('nan', '')})"
                    
            lease_options[l_id] = f"{' & '.join(t_names) if t_names else 'Άγνωστος'} | {prop_address}"

    # Ορισμός Καρτελών - Βάζουμε το Matrix πρώτο!
    tab_matrix, tab_new, tab_list, tab_edit = st.tabs([
        "📊 Ετήσια Επισκόπηση", "➕ Νέα Είσπραξη", "📋 Ιστορικό", "✏️ Επεξεργασία"
    ])

    # --- 1. ΕΤΗΣΙΑ ΕΠΙΣΚΟΠΗΣΗ (ΑΝΤΙΓΡΑΦΟ ΤΟΥ EXCEL) ---
    with tab_matrix:
        st.subheader("Συγκεντρωτικός Πίνακας Ελέγχου")
        st.caption("Μια ματιά στις πληρωμές όλων των μηνών για το επιλεγμένο έτος.")
        
        current_year = datetime.today().year
        selected_year = st.selectbox("Επιλογή Έτους", [current_year - 1, current_year, current_year + 1, current_year + 2], index=1)
        
        if leases_df.empty:
            st.info("Δεν υπάρχουν ενεργές μισθώσεις.")
        else:
            matrix_data = []
            months = [("Ιαν", 1), ("Φεβ", 2), ("Μαρ", 3), ("Απρ", 4), ("Μάι", 5), ("Ιουν", 6), 
                      ("Ιουλ", 7), ("Αυγ", 8), ("Σεπ", 9), ("Οκτ", 10), ("Νοε", 11), ("Δεκ", 12)]
            
            # Μετατροπή ημερομηνιών των πληρωμών (μία φορά για ταχύτητα)
            if not payments_df.empty:
                payments_df['Date_Obj'] = pd.to_datetime(payments_df['Date_Received'], errors='coerce')
            
            for _, lease in leases_df.iterrows():
                l_id = str(lease.get("Lease_ID", ""))
                
                # --- Στοιχεία Μίσθωσης ---
                p_id = str(lease.get("Property_ID", ""))
                prop_charact = "-"
                if not properties_df.empty:
                    p_match = properties_df[properties_df["Property_ID"] == p_id]
                    if not p_match.empty: prop_charact = f"{str(p_match.iloc[0].get('Χαρακτηριστικό', '')).replace('nan','')} ({str(p_match.iloc[0].get('Διεύθυνση', '')).replace('nan','')})"
                
                t_names = []
                for tid_clean in [t.strip() for t in str(lease.get("Tenant_ID", "")).split(',') if t.strip()]:
                    t_match = tenants_df[tenants_df["Tenant_ID"] == tid_clean]
                    if not t_match.empty: t_names.append(f"{str(t_match.iloc[0].get('Επώνυμο', '')).replace('nan','')} {str(t_match.iloc[0].get('Όνομα', '')).replace('nan','')}")
                tenant_name = " & ".join(t_names) if t_names else "Άγνωστος"
                
                rent_val = pd.to_numeric(str(lease.get('Monthly_Rent', '0')).replace(',', '.'), errors='coerce')
                if pd.isna(rent_val): rent_val = 0.0
                
                row_data = {
                    "Ακίνητο": prop_charact,
                    "Ενοικιαστής": tenant_name,
                    "Μίσθωμα": f"{rent_val:.2f} €".replace('.', ','),
                    "Λήξη": str(lease.get("End_Date", "-"))
                }
                
                # --- Υπολογισμός Μηνών ---
                for m_name, m_num in months:
                    if payments_df.empty:
                        row_data[m_name] = "❌ Εκκρεμεί"
                        continue
                        
                    # Φιλτράρισμα πληρωμών για το συγκεκριμένο συμβόλαιο, ενοίκιο, έτος και μήνα
                    p_month = payments_df[
                        (payments_df['Lease_ID'] == l_id) & 
                        (payments_df['Payment_Type'] == 'Ενοίκιο') &
                        (payments_df['Date_Obj'].dt.year == selected_year) & 
                        (payments_df['Date_Obj'].dt.month == m_num)
                    ]
                    
                    total_paid = pd.to_numeric(p_month['Amount'].astype(str).str.replace(',', '.'), errors='coerce').sum()
                    
                    if total_paid == 0:
                        row_data[m_name] = "❌ Εκκρεμεί"
                    elif total_paid < rent_val:
                        row_data[m_name] = f"⚠️ {total_paid:.2f}€".replace('.', ',')
                    else:
                        # Παίρνουμε το όνομα της τράπεζας από την τελευταία πληρωμή του μήνα
                        last_bank = str(p_month.iloc[-1].get('Bank_Account', 'Εξοφλήθη')).replace('nan', 'Εξοφλήθη')
                        row_data[m_name] = f"✅ {last_bank}"
                        
                matrix_data.append(row_data)
                
            # Εμφάνιση του Native Dataframe (Με Scroll Bar)
            st.dataframe(pd.DataFrame(matrix_data), use_container_width=True, hide_index=True)

    # --- 2. ΝΕΑ ΠΛΗΡΩΜΗ ---
    with tab_new:
        if not lease_options: st.info("Δεν υπάρχουν ενεργές μισθώσεις.")
        else:
            with st.form("new_payment_form", clear_on_submit=True):
                selected_lease_id = st.selectbox("Επιλογή Μίσθωσης / Ενοικιαστών *", options=list(lease_options.keys()), format_func=lambda x: lease_options[x])
                col1, col2 = st.columns(2)
                with col1: payment_type = st.selectbox("Είδος Οφειλής *", ["Ενοίκιο", "Νερό", "Κοινόχρηστα", "Ρεύμα", "Άλλο"])
                with col2: amount_input = st.text_input("Ποσό (€) *", value="0")
                col3, col4 = st.columns(2)
                with col3: date_received = st.date_input("Ημερομηνία Είσπραξης *", value=date.today())
                with col4: bank_account = st.selectbox("Τράπεζα / Τρόπος *", ["Εθνική Τράπεζα", "Eurobank", "Alpha Bank", "Τράπεζα Πειραιώς", "Μετρητά", "Άλλο"])

                if st.form_submit_button("Αποθήκευση Είσπραξης", use_container_width=True):
                    amt_val = pd.to_numeric(amount_input.replace(',', '.'), errors='coerce')
                    if pd.isna(amt_val): amt_val = 0.0
                    if selected_lease_id and amt_val > 0:
                        try:
                            gsheets_service.add_payment([f"PAY-{uuid.uuid4().hex[:6].upper()}", selected_lease_id, payment_type, amount_input, date_received.strftime("%Y-%m-%d"), bank_account])
                            st.success(f"Η είσπραξη καταχωρήθηκε επιτυχώς!")
                        except Exception as e: st.error(f"Σφάλμα: {e}")
                    else: st.warning("Παρακαλώ εισάγετε έγκυρο ποσό μεγαλύτερο του μηδενός.")

    # --- 3. ΙΣΤΟΡΙΚΟ (NATIVE DATAFRAME) ---
    with tab_list:
        if payments_df.empty: st.info("Δεν έχουν καταγραφεί εισπράξεις.")
        else:
            pay_list_data = []
            for _, row in payments_df.iterrows():
                amt_val = pd.to_numeric(str(row.get('Amount', '0')).replace(',', '.'), errors='coerce')
                if pd.isna(amt_val): amt_val = 0.0
                pay_list_data.append({
                    "Ημερομηνία": row.get("Date_Received", ""),
                    "Μίσθωση / Ενοικιαστής": lease_options.get(str(row.get("Lease_ID", "")), "Διαγραμμένη Μίσθωση"),
                    "Είδος": row.get("Payment_Type", ""),
                    "Ποσό": f"{amt_val:.2f} €".replace('.', ','),
                    "Μέθοδος": row.get("Bank_Account", "")
                })
            pay_list_data.reverse() # Τα πιο πρόσφατα πάνω-πάνω
            st.dataframe(pd.DataFrame(pay_list_data), use_container_width=True, hide_index=True)

    # --- 4. ΕΠΕΞΕΡΓΑΣΙΑ ΠΛΗΡΩΜΗΣ ---
    with tab_edit:
        if payments_df.empty: st.warning("Δεν υπάρχουν πληρωμές.")
        else:
            p_edit_opts = {str(r.get("Payment_ID", "")): f"{str(r.get('Date_Received', ''))} | {str(r.get('Payment_Type', ''))} {str(r.get('Amount', ''))}€" for _, r in payments_df.iterrows()}
            selected_pay_edit = st.selectbox("Επιλέξτε Πληρωμή προς Επεξεργασία", options=list(p_edit_opts.keys()), format_func=lambda x: p_edit_opts[x])
            
            if selected_pay_edit:
                sel_pay = payments_df[payments_df["Payment_ID"] == selected_pay_edit].iloc[0]
                l_keys = list(lease_options.keys())
                try: l_idx = l_keys.index(str(sel_pay.get("Lease_ID", "")))
                except: l_idx = 0
                try: pay_date = datetime.strptime(str(sel_pay.get("Date_Received", "")), "%Y-%m-%d").date()
                except: pay_date = date.today()

                with st.form("edit_pay_form"):
                    e_lease = st.selectbox("Μίσθωση *", options=l_keys, index=l_idx, format_func=lambda x: lease_options.get(x, x))
                    type_opts = ["Ενοίκιο", "Νερό", "Κοινόχρηστα", "Ρεύμα", "Άλλο"]
                    curr_type = str(sel_pay.get("Payment_Type", ""))
                    bank_opts = ["Εθνική Τράπεζα", "Eurobank", "Alpha Bank", "Τράπεζα Πειραιώς", "Μετρητά", "Άλλο"]
                    curr_bank = str(sel_pay.get("Bank_Account", ""))

                    ec1, ec2 = st.columns(2)
                    with ec1: e_type = st.selectbox("Είδος Οφειλής *", type_opts, index=type_opts.index(curr_type) if curr_type in type_opts else 0)
                    with ec2: e_amount = st.text_input("Ποσό (€) *", value=str(sel_pay.get("Amount", "")).replace('.', ','))
                    
                    ec3, ec4 = st.columns(2)
                    with ec3: e_date_rec = st.date_input("Ημερομηνία Είσπραξης *", value=pay_date)
                    with ec4: e_bank = st.selectbox("Τράπεζα / Τρόπος *", bank_opts, index=bank_opts.index(curr_bank) if curr_bank in bank_opts else 0)
                    
                    upd_p_btn = st.form_submit_button("Αποθήκευση Αλλαγών", type="primary")
                    
                if st.button("🗑️ Οριστική Διαγραφή Πληρωμής"):
                    try:
                        gsheets_service.delete_payment(selected_pay_edit)
                        st.success("Η πληρωμή διαγράφηκε! Ανανεώστε τη σελίδα.")
                    except Exception as e: st.error(f"Σφάλμα: {e}")

                if upd_p_btn:
                    amt_val = pd.to_numeric(e_amount.replace(',', '.'), errors='coerce')
                    if pd.isna(amt_val): amt_val = 0.0
                    if e_lease and amt_val > 0:
                        try:
                            gsheets_service.update_payment(selected_pay_edit, [selected_pay_edit, e_lease, e_type, e_amount, e_date_rec.strftime("%Y-%m-%d"), e_bank])
                            st.success("Οι αλλαγές αποθηκεύτηκαν! Ανανεώστε τη σελίδα.")
                        except Exception as e: st.error(f"Σφάλμα: {e}")
                    else: st.warning("Παρακαλώ εισάγετε έγκυρο ποσό.")
