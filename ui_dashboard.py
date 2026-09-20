import streamlit as st
import gsheets_service
import pandas as pd
from datetime import datetime
import notification_service

def show():
    st.header("Επισκόπηση & Ειδοποιήσεις")
    
    try:
        leases_df = gsheets_service.fetch_all_leases()
        properties_df = gsheets_service.fetch_all_properties()
        tenants_df = gsheets_service.fetch_all_tenants()
    except Exception as e:
        st.error("Αδυναμία φόρτωσης δεδομένων.")
        return

    if leases_df.empty:
        st.info("Το μητρώο είναι άδειο. Προσθέστε ακίνητα και μισθώσεις.")
        return

    # --- 1. ΣΥΓΚΕΝΤΡΩΤΙΚΟΣ ΠΙΝΑΚΑΣ ΜΙΣΘΩΣΕΩΝ ---
    st.subheader("📋 Ενεργές Μισθώσεις")
    table_data = []
    
    for _, lease in leases_df.iterrows():
        # Εύρεση Χαρακτηριστικού Ακινήτου
        prop_match = properties_df[properties_df['Property_ID'] == lease['Property_ID']]
        charact = str(prop_match.iloc[0].get('Χαρακτηριστικό', '-')) if not prop_match.empty else '-'
        
        # Κατασκευή string ιδιοκτητών (π.χ. Γιώργος (Επικαρπία 100%) | Μαρία (Ψιλή 100%))
        owners_str = []
        for i in range(1, 4):
            n = lease.get(f'Name_{i}', '')
            s = lease.get(f'Surname_{i}', '')
            r = lease.get(f'Right_{i}', '')
            p = lease.get(f'Perc_{i}', 0)
            if str(n).strip() and float(p) > 0:
                owners_str.append(f"{n} {s} ({r} {p}%)")
                
        table_data.append({
            "Ακίνητο": charact,
            "Ιδιοκτήτες / Δικαιώματα": " | ".join(owners_str),
            "Έναρξη": lease.get('Start_Date', ''),
            "Λήξη": lease.get('End_Date', ''),
            "Μίσθωμα": f"{float(lease.get('Monthly_Rent', 0)):.2f} €"
        })
        
    st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)
    st.divider()

    # --- 2. ΒΑΣΙΚΑ KPI & ΕΙΔΟΠΟΙΗΣΕΙΣ (Υφιστάμενα) ---
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="Σύνολο Ακινήτων", value=len(properties_df))
    with col2:
        st.metric(label="Ενεργές Μισθώσεις", value=len(leases_df))
    with col3:
        leases_df['Monthly_Rent'] = pd.to_numeric(leases_df['Monthly_Rent'], errors='coerce').fillna(0)
        st.metric(label="Συνολικό Ενοίκιο (Μήνα)", value=f"{leases_df['Monthly_Rent'].sum():,.2f} €")

    st.subheader("⚠️ Επερχόμενες Λήξεις Μισθώσεων")
    today = datetime.today()
    expiring_count = 0
    leases_df['End_Date_Obj'] = pd.to_datetime(leases_df['End_Date'], errors='coerce')
    
    for index, row in leases_df.iterrows():
        end_date = row['End_Date_Obj']
        if pd.notnull(end_date):
            days_rem = (end_date - today).days
            if days_rem <= 60:
                expiring_count += 1
                t_match = tenants_df[tenants_df["Tenant_ID"] == row["Tenant_ID"]]
                t_name = f"{t_match.iloc[0]['Όνομα']} {t_match.iloc[0]['Επώνυμο']}" if not t_match.empty else "Άγνωστος"
                p_match = properties_df[properties_df["Property_ID"] == row["Property_ID"]]
                p_addr = f"{p_match.iloc[0]['Διεύθυνση']} {p_match.iloc[0]['Αριθμός']}" if not p_match.empty else "Άγνωστο"
                
                if days_rem < 0:
                    st.error(f"ΕΛΗΞΕ ΠΡΙΝ {-days_rem} ΜΕΡΕΣ: {p_addr} | Ενοικιαστής: {t_name}")
                else:
                    st.warning(f"ΛΗΓΕΙ ΣΕ {days_rem} ΜΕΡΕΣ: {p_addr} | Ενοικιαστής: {t_name}")

    if expiring_count == 0:
        st.success("Καμία μίσθωση δεν λήγει τις επόμενες 60 ημέρες. Όλα βαίνουν καλώς! 🌿")
    st.divider()

    # --- 3. ΦΟΡΟΛΟΓΙΚΗ ΕΚΤΙΜΗΣΗ (ΕΤΗΣΙΑ) ΑΝΑ ΙΔΙΟΚΤΗΤΗ ---
    st.subheader("💡 Εκτίμηση Φόρου & Καθαρών Εσόδων (Ετήσια)")
    st.caption("Υπολογίζεται με βάση την κλίμακα 15%-35%-45% μόνο για όσους έχουν Επικαρπία ή Πλήρη Κυριότητα.")
    
    income_per_owner = {}
    
    for _, lease in leases_df.iterrows():
        rent = float(lease.get('Monthly_Rent', 0))
        for i in range(1, 4):
            afm = str(lease.get(f'AFM_{i}', '')).strip()
            name = f"{lease.get(f'Name_{i}', '')} {lease.get(f'Surname_{i}', '')}".strip()
            right = str(lease.get(f'Right_{i}', ''))
            perc = float(lease.get(f'Perc_{i}', 0) or 0)
            
            # Το εισόδημα πηγαίνει μόνο σε Επικαρπία / Πλήρη
            if afm and perc > 0 and right in ["Πλήρης Κυριότητα", "Επικαρπία"]:
                share_of_rent = rent * (perc / 100.0)
                if afm not in income_per_owner:
                    income_per_owner[afm] = {"name": name, "monthly": 0}
                income_per_owner[afm]["monthly"] += share_of_rent

    if not income_per_owner:
        st.info("Δεν βρέθηκαν ιδιοκτήτες με δικαίωμα είσπραξης ενοικίου (Επικαρπία/Πλήρης) στις ενεργές μισθώσεις.")

    for afm, data in income_per_owner.items():
        annual_inc = data["monthly"] * 12
        
        # Κλιμακωτός Φόρος Εισοδήματος (Ακίνητα)
        tax = 0
        if annual_inc <= 12000:
            tax = annual_inc * 0.15
        elif annual_inc <= 35000:
            tax = (12000 * 0.15) + ((annual_inc - 12000) * 0.35)
        else:
            tax = (12000 * 0.15) + (23000 * 0.35) + ((annual_inc - 35000) * 0.45)
            
        net_inc = annual_inc - tax
        
        st.info(f"**{data['name']} (ΑΦΜ: {afm})**\n\n"
                f"Ετήσια Μικτά: **{annual_inc:,.2f} €** | "
                f"Εκτιμώμενος Φόρος: **{tax:,.2f} €** | "
                f"Καθαρά Έσοδα: **{net_inc:,.2f} €**")
