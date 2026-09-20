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

    if leases_df.empty:
        st.info("Δεν υπάρχουν ενεργές μισθώσεις για να παρακολουθήσετε πληρωμές.")
        return

    # Έξυπνη διαχείριση παλαιών δεδομένων (αν δεν έχουν For_Month/For_Year)
    if not payments_df.empty:
        if "For_Month" not in payments_df.columns: payments_df["For_Month"] = ""
        if "For_Year" not in payments_df.columns: payments_df["For_Year"] = ""
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
    else:
        payments_df = pd.DataFrame(columns=['Payment_ID', 'Lease_ID', 'Payment_Type', 'Amount', 'Date_Received', 'Bank_Account', 'For_Month', 'For_Year', 'Calc_Month', 'Calc_Year'])

    # State Initialization για το κλικ στο Matrix
    if "payment_modal" not in st.session_state:
        st.session_state.payment_modal = None

    # Επιλογή Έτους
    current_year = datetime.today().year
    selected_year = st.selectbox("Επιλογή Έτους", [current_year - 1, current_year, current_year + 1, current_year + 2], index=1)
    
    st.subheader(f"Πίνακας Ελέγχου - {selected_year}")
    st.caption("Κάντε κλικ στο εικονίδιο ενός μήνα για να προβάλετε, να προσθέσετε ή να διαγράψετε οφειλές.")

    # --- Επικεφαλίδες Πίνακα (Grid) ---
    months = ["Ιαν", "Φεβ", "Μαρ", "Απρ", "Μάι", "Ιουν", "Ιουλ", "Αυγ", "Σεπ", "Οκτ", "Νοε", "Δεκ"]
    cols = st.columns([3] + [1]*12)
    cols[0].markdown("**Ακίνητο & Ενοικιαστής**")
    for i, m_name in enumerate(months):
        cols[i+1].markdown(f"**{m_name}**")

    # --- Γέμισμα του Matrix ---
    for _, lease in leases_df.iterrows():
        l_id = str(lease.get("Lease_ID", ""))
        p_id = str(lease.get("Property_ID", ""))
        
        # Πληροφορίες Ακινήτου
        prop_charact = "-"
        if not properties_df.empty:
            p_match = properties_df[properties_df["Property_ID"] == p_id]
            if not p_match.empty: prop_charact = str(p_match.iloc[0].get('Χαρακτηριστικό', '-'))
            
        # Πληροφορίες Ενοικιαστών
        t_names = []
        for tid_clean in [t.strip() for t in str(lease.get("Tenant_ID", "")).split(',') if t.strip()]:
            t_match = tenants_df[tenants_df["Tenant_ID"] == tid_clean]
            if not t_match.empty: t_names.append(f"{str(t_match.iloc[0].get('Επώνυμο', '')).replace('nan','')} {str(t_match.iloc[0].get('Όνομα', '')).replace('nan','')}")
        tenant_name = " & ".join(t_names) if t_names else "Άγνωστος"
        
        expected_rent = pd.to_numeric(str(lease.get('Monthly_Rent', '0')).replace(',', '.'), errors='coerce')
        if pd.isna(expected_rent): expected_rent = 0.0

        row_cols = st.columns([3] + [1]*12)
        row_cols[0].write(f"🏠 {prop_charact}\n👤 {tenant_name}")

        # Κουμπιά Μηνών
        for m_idx in range(1, 13):
            # Φιλτράρισμα πληρωμών για αυτό το συμβόλαιο, μήνα και έτος
            p_month = payments_df[
                (payments_df['Lease_ID'] == l_id) & 
                (payments_df['Calc_Month'] == str(m_idx)) &
                (payments_df['Calc_Year'] == str(selected_year))
            ]
            
            # Υπολογισμός συνολικού ενοικίου που έχει πληρωθεί
            rent_paid = pd.to_numeric(p_month[p_month['Payment_Type'] == 'Ενοίκιο']['Amount'].astype(str).str.replace(',', '.'), errors='coerce').sum()
            
            if rent_paid >= expected_rent and expected_rent > 0:
                status_icon = "✅"
            elif rent_paid > 0:
                status_icon = "⚠️"
            else:
                status_icon = "❌"
                
            # Το κουμπί λειτουργεί ως σύνδεσμος για το άνοιγμα του μενού από κάτω
            if row_cols[m_idx].button(status_icon, key=f"btn_{l_id}_{m_idx}_{selected_year}", use_container_width=True):
                st.session_state.payment_modal = {
                    "lease_id": l_id, 
                    "month": m_idx, 
                    "year": selected_year,
                    "prop_charact": prop_charact,
                    "tenant_name": tenant_name,
                    "expected_rent": expected_rent
                }
                st.rerun()

    # ==========================================
    # --- ΠΑΡΑΘΥΡΟ ΔΙΑΧΕΙΡΙΣΗΣ (MODAL VIEW) ---
    # ==========================================
    if st.session_state.payment_modal:
        m_info = st.session_state.payment_modal
        st.markdown("---")
        
        col_t, col_b = st.columns([4, 1])
        with col_t:
            st.markdown(f"### ⚙️ Διαχείριση Μήνα: **{months[m_info['month']-1]} {m_info['year']}**")
            st.caption(f"🏠 {m_info['prop_charact']} | 👤 {m_info['tenant_name']}")
        with col_b:
            if st.button("❌ Κλείσιμο Καρτέλας", use_container_width=True):
                st.session_state.payment_modal = None
                st.rerun()

        # 1. Υπάρχουσες Οφειλές/Πληρωμές
        p_month_data = payments_df[
            (payments_df['Lease_ID'] == m_info['lease_id']) & 
            (payments_df['Calc_Month'] == str(m_info['month'])) &
            (payments_df['Calc_Year'] == str(m_info['year']))
        ]
        
        rent_paid = pd.to_numeric(p_month_data[p_month_data['Payment_Type'] == 'Ενοίκιο']['Amount'].astype(str).str.replace(',', '.'), errors='coerce').sum()
        
        # Εμφάνιση συνοπτικού υπολοίπου
        st.info(f"**Σύνοψη Ενοικίου:** Αναμενόμενο: **{m_info['expected_rent']:.2f}€** | Έχει Πληρωθεί: **{rent_paid:.2f}€** | Υπόλοιπο: **{max(0, m_info['expected_rent'] - rent_paid):.2f}€**")
        
        st.markdown("#### 📋 Ήδη Καταχωρημένες Εισπράξεις")
        if p_month_data.empty:
            st.write("Καμία είσπραξη για αυτόν τον μήνα.")
        else:
            for _, p_row in p_month_data.iterrows():
                pc1, pc2, pc3, pc4 = st.columns([2, 2, 2, 1])
                amt = pd.to_numeric(str(p_row['Amount']).replace(',', '.'), errors='coerce')
                if pd.isna(amt): amt = 0.0
                
                pc1.write(f"💳 **{p_row['Payment_Type']}** | {amt:.2f}€")
                pc2.write(f"📅 Ημ/νία: {p_row['Date_Received']}")
                pc3.write(f"🏦 {p_row['Bank_Account']}")
                if pc4.button("🗑️ Διαγραφή", key=f"del_{p_row['Payment_ID']}", use_container_width=True):
                    try:
                        gsheets_service.delete_payment(p_row['Payment_ID'])
                        st.success("Διαγράφηκε!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Σφάλμα: {e}")

        # 2. Φόρμα Προσθήκης Νέας Πληρωμής ΣΤΟΝ ΣΥΓΚΕΚΡΙΜΕΝΟ ΜΗΝΑ
        st.markdown("#### ➕ Προσθήκη Νέας Είσπραξης")
        with st.form("add_monthly_payment_form", clear_on_submit=True):
            fc1, fc2 = st.columns(2)
            with fc1: p_type = st.selectbox("Είδος Οφειλής *", ["Ενοίκιο", "Νερό", "Κοινόχρηστα", "Ρεύμα", "Άλλο"])
            with fc2: 
                # Αν είναι ενοίκιο, προτείνουμε το υπόλοιπο που χρωστάει. Αλλιώς 0.
                default_amt = str(max(0, m_info['expected_rent'] - rent_paid)).replace('.', ',') if p_type == "Ενοίκιο" else "0"
                p_amt = st.text_input("Ποσό (€) *", value=default_amt)
                
            fc3, fc4 = st.columns(2)
            with fc3: p_date = st.date_input("Ημερομηνία Είσπραξης *", value=date.today())
            with fc4: p_bank = st.selectbox("Τράπεζα / Τρόπος *", ["Εθνική Τράπεζα", "Eurobank", "Alpha Bank", "Τράπεζα Πειραιώς", "Μετρητά", "Άλλο"])
            
            if st.form_submit_button("Αποθήκευση Είσπραξης", use_container_width=True):
                amt_val = pd.to_numeric(p_amt.replace(',', '.'), errors='coerce')
                if pd.isna(amt_val): amt_val = 0.0
                if amt_val > 0:
                    try:
                        # Στέλνουμε 8 πεδία στο Google Sheet (τα τελευταία 2 είναι ο μήνας και το έτος)
                        row_data = [
                            f"PAY-{uuid.uuid4().hex[:6].upper()}", 
                            m_info['lease_id'], 
                            p_type, 
                            p_amt, 
                            p_date.strftime("%Y-%m-%d"), 
                            p_bank, 
                            str(m_info['month']), 
                            str(m_info['year'])
                        ]
                        gsheets_service.add_payment(row_data)
                        st.success("Η είσπραξη καταχωρήθηκε! Ανανεώστε τη σελίδα.")
                        st.rerun() # Αυτόματη ανανέωση του Matrix!
                    except Exception as e:
                        st.error(f"Σφάλμα: {e}")
                else:
                    st.warning("Παρακαλώ εισάγετε έγκυρο ποσό.")
