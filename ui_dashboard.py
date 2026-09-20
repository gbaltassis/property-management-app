import streamlit as st
import gsheets_service
import pandas as pd
from datetime import datetime

COMMON_CSS = """
<style>
    .custom-table {
        width: 100% !important;
        border-collapse: collapse;
        font-family: sans-serif;
        font-size: 14px;
        margin-bottom: 2rem;
    }
    .custom-table th {
        text-align: left !important;
        background-color: #f0f2f6;
        padding: 12px;
        border-bottom: 1px solid #e6e9ef;
        color: #31333F;
    }
    .custom-table td {
        text-align: left !important;
        word-wrap: break-word !important;
        white-space: normal !important;
        padding: 12px;
        border-bottom: 1px solid #e6e9ef;
        color: #31333F;
        vertical-align: top;
    }
</style>
"""

def show():
    st.markdown(COMMON_CSS, unsafe_allow_html=True)
    st.header("Επισκόπηση & Ειδοποιήσεις")
    
    try:
        leases_df = gsheets_service.fetch_all_leases()
        properties_df = gsheets_service.fetch_all_properties()
        tenants_df = gsheets_service.fetch_all_tenants()
    except Exception as e:
        st.error(f"Αδυναμία φόρτωσης δεδομένων: {e}")
        return

    if leases_df.empty:
        st.info("Το μητρώο είναι άδειο. Προσθέστε ακίνητα και μισθώσεις.")
        return

    today = datetime.today()
    leases_df['End_Date_Obj'] = pd.to_datetime(leases_df['End_Date'], errors='coerce')
    
    active_leases_data = []
    expiring_leases_data = []
    expired_leases_data = []
    
    total_active_rent = 0.0
    active_leases_count = 0
    income_per_owner = {}
    
    for _, lease in leases_df.iterrows():
        prop_match = properties_df[properties_df['Property_ID'] == lease['Property_ID']]
        if not prop_match.empty:
            prop = prop_match.iloc[0]
            charact = str(prop.get('Χαρακτηριστικό', '-'))
            owners_str = []
            
            for i in range(1, 4):
                n = str(prop.get(f'Name_{i}', '')).strip()
                s = str(prop.get(f'Surname_{i}', '')).strip()
                r = str(prop.get(f'Right_{i}', '')).strip()
                p_raw = str(prop.get(f'Perc_{i}', '')).replace(',', '.')
                p = pd.to_numeric(p_raw, errors='coerce')
                if pd.isna(p): p = 0.0

                if n and p > 0:
                    p_display = str(p).replace('.', ',')
                    if p_display.endswith(',0'): p_display = p_display[:-2]
                    owners_str.append(f"{n} {s} ({r} {p_display}%)")
        else:
            charact = "-"
            owners_str = []

        rent_raw = str(lease.get('Monthly_Rent', '0')).replace(',', '.')
        safe_rent = pd.to_numeric(rent_raw, errors='coerce')
        if pd.isna(safe_rent): safe_rent = 0.0
        
        t_ids = str(lease.get("Tenant_ID", "")).split(',')
        t_names = []
        for tid in t_ids:
            tid_clean = tid.strip()
            if tid_clean:
                tenants_df['Tenant_ID'] = tenants_df['Tenant_ID'].astype(str)
                t_match = tenants_df[tenants_df["Tenant_ID"] == tid_clean]
                if not t_match.empty:
                    t_names.append(f"{t_match.iloc[0].get('Όνομα', '')} {t_match.iloc[0].get('Επώνυμο', '')}")
        tenant_name = " & ".join(t_names) if t_names else "Άγνωστος"
        
        end_date = lease['End_Date_Obj']
        start_date = str(lease.get('Start_Date', ''))
        days_rem = (end_date - today).days if pd.notnull(end_date) else 999
        
        row_dict = {
            "Ακίνητο": charact,
            "Ιδιοκτήτες / Δικαιώματα": "<br>".join(owners_str) if owners_str else "-",
            "Ενοικιαστής": tenant_name,
            "Έναρξη": start_date,
            "Λήξη": str(end_date.date()) if pd.notnull(end_date) else "-",
            "Μίσθωμα": f"{safe_rent:.2f} €".replace('.', ',')
        }
        
        if days_rem > 30:
            active_leases_data.append(row_dict)
            active_leases_count += 1
            total_active_rent += safe_rent
            
            if not prop_match.empty:
                for i in range(1, 4):
                    afm = str(prop.get(f'AFM_{i}', '')).strip()
                    if len(afm) == 8: afm = "0" + afm 
                    
                    name = f"{str(prop.get(f'Name_{i}', '')).strip()} {str(prop.get(f'Surname_{i}', '')).strip()}".strip()
                    right = str(prop.get(f'Right_{i}', '')).strip()
                    p_raw = str(prop.get(f'Perc_{i}', '')).replace(',', '.')
                    perc = pd.to_numeric(p_raw, errors='coerce')
                    if pd.isna(perc): perc = 0.0
                    
                    if afm and perc > 0 and right in ["Πλήρης Κυριότητα", "Επικαρπία"]:
                        share_of_rent = safe_rent * (perc / 100.0)
                        if afm not in income_per_owner:
                            income_per_owner[afm] = {"name": name, "monthly": 0}
                        income_per_owner[afm]["monthly"] += share_of_rent
                        
        elif 0 <= days_rem <= 30:
            row_dict["Ημέρες ως Λήξη"] = days_rem
            expiring_leases_data.append(row_dict)
            active_leases_count += 1
            total_active_rent += safe_rent
        else:
            row_dict["Ημέρες Ληγμένη"] = abs(days_rem)
            expired_leases_data.append(row_dict)

    # --- 1. ΒΑΣΙΚΑ KPI ---
    col1, col2, col3 = st.columns(3)
    with col1: st.metric(label="Σύνολο Ακινήτων", value=len(properties_df))
    with col2: st.metric(label="Ενεργές Μισθώσεις", value=active_leases_count)
    with col3: st.metric(label="Συνολικό Ενοίκιο (Μήνα)", value=f"{total_active_rent:,.2f} €".replace('.', ','))
    st.divider()

    # --- 2. ΠΙΝΑΚΕΣ ΣΕ HTML ΜΟΡΦΗ ---
    st.subheader("📋 Ενεργές Μισθώσεις (> 30 ημέρες)")
    if active_leases_data:
        st.write(pd.DataFrame(active_leases_data).to_html(classes='custom-table', escape=False, index=False, justify='left'), unsafe_allow_html=True)
    else:
        st.info("Δεν υπάρχουν μισθώσεις με λήξη άνω των 30 ημερών.")
        
    st.subheader("⚠️ Επερχόμενες Λήξεις Μισθώσεων (0-30 ημέρες)")
    if expiring_leases_data:
        st.write(pd.DataFrame(expiring_leases_data).to_html(classes='custom-table', escape=False, index=False, justify='left'), unsafe_allow_html=True)
    else:
        st.success("Καμία μίσθωση δεν λήγει τις επόμενες 30 ημέρες.")
        
    st.subheader("❌ Ληγμένες Μισθώσεις")
    if expired_leases_data:
        st.write(pd.DataFrame(expired_leases_data).to_html(classes='custom-table', escape=False, index=False, justify='left'), unsafe_allow_html=True)
    else:
        st.success("Δεν υπάρχουν ληγμένες μισθώσεις στο σύστημα.")
    st.divider()

    # --- 3. ΦΟΡΟΛΟΓΙΚΗ ΕΚΤΙΜΗΣΗ ---
    st.subheader("💡 Εκτίμηση Φόρου & Καθαρών Εσόδων (Ετήσια)")
    
    if not income_per_owner:
        st.info("Δεν βρέθηκαν ιδιοκτήτες με δικαίωμα (Επικαρπία/Πλήρης) στις ενεργές μισθώσεις.")
    else:
        for afm, data in income_per_owner.items():
            annual_inc = data["monthly"] * 12
            tax = 0
            
            if annual_inc <= 12000:
                tax = annual_inc * 0.15
            elif annual_inc <= 24000:
                tax = (12000 * 0.15) + ((annual_inc - 12000) * 0.25)
            elif annual_inc <= 35000:
                tax = (12000 * 0.15) + (12000 * 0.25) + ((annual_inc - 24000) * 0.35)
            else:
                tax = (12000 * 0.15) + (12000 * 0.25) + (11000 * 0.35) + ((annual_inc - 35000) * 0.45)
                
            net_inc = annual_inc - tax
            
            st.info(f"**{data['name']} (ΑΦΜ: {afm})**\n\n"
                    f"Ετήσια Μικτά: **{annual_inc:,.2f} €** | "
                    f"Εκτιμώμενος Φόρος: **{tax:,.2f} €** | "
                    f"Καθαρά Έσοδα: **{net_inc:,.2f} €**")
