import streamlit as st
import gsheets_service
import uuid
import pandas as pd
from datetime import date, datetime

def show():
    st.header("Μισθώσεις")
    
    try:
        properties_df = gsheets_service.fetch_all_properties()
        tenants_df = gsheets_service.fetch_all_tenants()
        leases_df = gsheets_service.fetch_all_leases()
    except:
        st.error("Σφάλμα σύνδεσης.")
        return

    # ΑΛΛΑΓΗ ΣΕΙΡΑΣ ΕΔΩ: Πρώτα το tab_list, μετά το tab_new
    tab_list, tab_new, tab_edit = st.tabs(["📋 Υπάρχουσες Μισθώσεις", "➕ Νέα Μίσθωση", "✏️ Επεξεργασία Μίσθ."])

    with tab_list:
        if leases_df.empty: st.info("Δεν υπάρχουν καταχωρημένες μισθώσεις.")
        else:
            today = datetime.today()
            leases_df['End_Date_Obj'] = pd.to_datetime(leases_df['End_Date'], errors='coerce')
            lease_list_data = []
            for _, row in leases_df.iterrows():
                p_match = properties_df[properties_df["Property_ID"] == str(row.get("Property_ID", ""))]
                prop_charact = str(p_match.iloc[0].get("Χαρακτηριστικό", "-")) if not p_match.empty else "-"
                
                t_names = []
                for tid_clean in [t.strip() for t in str(row.get("Tenant_ID", "")).split(',') if t.strip()]:
                    tenants_df['Tenant_ID'] = tenants_df['Tenant_ID'].astype(str)
                    t_match = tenants_df[tenants_df["Tenant_ID"] == tid_clean]
                    if not t_match.empty: t_names.append(f"{t_match.iloc[0].get('Όνομα', '')} {t_match.iloc[0].get('Επώνυμο', '')}")
                
                end_date = row['End_Date_Obj']
                days_rem = (end_date - today).days if pd.notnull(end_date) else 999
                
                if days_rem > 30: status = "🟢 Ενεργή"
                elif 0 <= days_rem <= 30: status = "🟡 Προς Ανανέωση"
                else: status = "🔴 Ληγμένη"

                rent_val = pd.to_numeric(str(row.get('Monthly_Rent', '0')).replace(',', '.'), errors='coerce')
                if pd.isna(rent_val): rent_val = 0.0

                lease_list_data.append({
                    "Κατάσταση": status,
                    "Ακίνητο": prop_charact,
                    "Ενοικιαστής": " & ".join(t_names) if t_names else "Άγνωστος",
                    "Έναρξη": row.get("Start_Date", "-"),
                    "Λήξη": row.get("End_Date", "-"),
                    "Μίσθωμα": f"{rent_val:.2f} €".replace('.', ','),
                })
            st.dataframe(pd.DataFrame(lease_list_data), use_container_width=True, hide_index=True)
    
    with tab_new:
        if properties_df.empty or tenants_df.empty: st.warning("Πρέπει να καταχωρήσετε Ακίνητο και Ενοικιαστή στο Μητρώο.")
        else:
            prop_options = {row["Property_ID"]: f"{row.get('Διεύθυνση','')} {row.get('Αριθμός','')} - {row.get('Χαρακτηριστικό', '')}" for _, row in properties_df.iterrows()}
            tenant_options = {row["Tenant_ID"]: f"{row.get('Όνομα', '')} {row.get('Επώνυμο', '')} (ΑΦΜ: {row.get('ΑΦΜ', '')})" for _, row in tenants_df.iterrows()}

            with st.form("new_lease_form", clear_on_submit=True):
                st.subheader("1. Αντιστοίχιση")
                selected_prop_id = st.selectbox("Ακίνητο *", options=list(prop_options.keys()), format_func=lambda x: prop_options[x])
                selected_tenant_ids = st.multiselect("Ενοικιαστής / Ενοικιαστές *", options=list(tenant_options.keys()), format_func=lambda x: tenant_options[x])
                
                st.subheader("2. Οικονομικοί Όροι")
                col1, col2 = st.columns(2)
                with col1:
                    start_date = st.date_input("Ημ/νία Έναρξης *", value=date.today())
                    rent_input = st.text_input("Μηνιαίο Μίσθωμα (€) *", value="0")
                with col2: end_date = st.date_input("Ημ/νία Λήξης *")
                    
                special_agreements, aade_url = st.text_area("Ειδικές Συμφωνίες"), st.text_input("Σύνδεσμος ΑΑΔΕ (URL)", placeholder="https://...")

                if st.form_submit_button("Αποθήκευση Μίσθωσης", use_container_width=True):
                    rent_val = pd.to_numeric(rent_input.replace(',', '.'), errors='coerce')
                    if pd.isna(rent_val): rent_val = 0.0
                    if rent_val > 0 and end_date > start_date and selected_tenant_ids:
                        try:
                            gsheets_service.add_lease([f"LS-{uuid.uuid4().hex[:6].upper()}", selected_prop_id, ",".join(selected_tenant_ids), start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), rent_input, special_agreements, aade_url])
                            st.success("Η μίσθωση αποθηκεύτηκε!")
                        except Exception as e: st.error(f"Σφάλμα: {e}")
                    else: st.warning("Ελέγξτε τις ημερομηνίες, το έγκυρο ποσό και επιλέξτε τουλάχιστον έναν ενοικιαστή.")
    

    with tab_edit:
        if leases_df.empty: st.warning("Δεν υπάρχουν μισθώσεις.")
        else:
            prop_options = {row["Property_ID"]: f"{row.get('Διεύθυνση','')} - {row.get('Χαρακτηριστικό', '')}" for _, row in properties_df.iterrows()}
            tenant_options = {row["Tenant_ID"]: f"{row.get('Όνομα', '')} {row.get('Επώνυμο', '')}" for _, row in tenants_df.iterrows()}
            
            l_edit_opts = {str(r.get("Lease_ID", "")): f"{str(r.get('Lease_ID', ''))} | {prop_options.get(str(r.get('Property_ID', '')), 'Άγνωστο Ακίνητο')}" for _, r in leases_df.iterrows()}
            selected_l_edit = st.selectbox("Επιλέξτε Μίσθωση", options=list(l_edit_opts.keys()), format_func=lambda x: l_edit_opts[x])
            
            if selected_l_edit:
                sel_lease = leases_df[leases_df["Lease_ID"] == selected_l_edit].iloc[0]
                p_keys = list(prop_options.keys())
                try: p_idx = p_keys.index(str(sel_lease.get("Property_ID", "")))
                except: p_idx = 0
                
                t_ids_clean = [t.strip() for t in str(sel_lease.get("Tenant_ID", "")).split(',') if t.strip() in tenant_options]

                try: s_date = datetime.strptime(str(sel_lease.get("Start_Date", "")), "%Y-%m-%d").date()
                except: s_date = date.today()
                try: e_date = datetime.strptime(str(sel_lease.get("End_Date", "")), "%Y-%m-%d").date()
                except: e_date = date.today()

                with st.form("edit_lease_form"):
                    e_prop = st.selectbox("Ακίνητο *", options=p_keys, index=p_idx, format_func=lambda x: prop_options.get(x, x))
                    e_tenants = st.multiselect("Ενοικιαστής / Ενοικιαστές *", options=list(tenant_options.keys()), default=t_ids_clean, format_func=lambda x: tenant_options[x])
                    
                    ec1, ec2 = st.columns(2)
                    with ec1: e_start = st.date_input("Ημ/νία Έναρξης *", value=s_date)
                    with ec2: e_end = st.date_input("Ημ/νία Λήξης *", value=e_date)
                    
                    e_rent = st.text_input("Μηνιαίο Μίσθωμα (€) *", value=str(sel_lease.get("Monthly_Rent", "")).replace('.', ','))
                    e_spec, e_url = st.text_area("Ειδικές Συμφωνίες", value=str(sel_lease.get("Special_Agreements", ""))), st.text_input("Σύνδεσμος ΑΑΔΕ (URL)", value=str(sel_lease.get("AADE_Document_URL", "")))
                    
                    upd_l_btn = st.form_submit_button("Αποθήκευση Αλλαγών", type="primary")
                    
                if st.button("🗑️ Οριστική Διαγραφή Μίσθωσης"):
                    try:
                        gsheets_service.delete_lease(selected_l_edit)
                        st.success("Η μίσθωση διαγράφηκε! Ανανεώστε τη σελίδα.")
                    except Exception as e: st.error(f"Σφάλμα διαγραφής: {e}")

                if upd_l_btn:
                    rent_val = pd.to_numeric(e_rent.replace(',', '.'), errors='coerce')
                    if pd.isna(rent_val): rent_val = 0.0
                    if rent_val > 0 and e_end > e_start and e_tenants:
                        try:
                            gsheets_service.update_lease(selected_l_edit, [selected_l_edit, e_prop, ",".join(e_tenants), e_start.strftime("%Y-%m-%d"), e_end.strftime("%Y-%m-%d"), e_rent, e_spec, e_url])
                            st.success("Οι αλλαγές αποθηκεύτηκαν! Ανανεώστε τη σελίδα.")
                        except Exception as e: st.error(f"Σφάλμα επεξεργασίας: {e}")
                    else: st.warning("Ελέγξτε τις ημερομηνίες, το ποσό και τους ενοικιαστές.")
