import streamlit as st
import gsheets_service
import pandas as pd
from datetime import datetime

COMMON_CSS = """<style>.custom-table { width: 100% !important; border-collapse: collapse; margin-bottom: 2rem; } .custom-table th { text-align: left !important; background-color: #f0f2f6; padding: 12px; border-bottom: 1px solid #e6e9ef; } .custom-table td { text-align: left !important; padding: 12px; border-bottom: 1px solid #e6e9ef; vertical-align: top; }</style>"""

def show():
    st.markdown(COMMON_CSS, unsafe_allow_html=True)
    st.header("Επισκόπηση & Ταμειακές Ροές")
    
    try:
        leases_df = gsheets_service.fetch_all_leases()
        properties_df = gsheets_service.fetch_all_properties()
        payments_df = gsheets_service.fetch_all_payments()
        try: expenses_df = gsheets_service.fetch_all_expenses()
        except: expenses_df = pd.DataFrame() # Fallback αν δεν το έφτιαξες σωστά
    except Exception as e:
        st.error(f"Αδυναμία φόρτωσης δεδομένων: {e}")
        return

    # --- SECTION 1: ΠΡΑΓΜΑΤΙΚΕΣ ΤΑΜΕΙΑΚΕΣ ΡΟΕΣ (CASH FLOW) ---
    st.subheader("💡 Πραγματικές Ταμειακές Ροές ανά Ιδιοκτήτη")
    current_year = datetime.today().year
    selected_year = st.selectbox("Ανάλυση Έτους:", [current_year - 1, current_year, current_year + 1], index=1)
    
    owner_finances = {} # Structure: { 'AFM': {'Name': '', 'Income': 0, 'ENFIA': 0, 'Prop_Expenses': 0} }

    # 1. Υπολογισμός Εσόδων ανά Ακίνητο -> Αναλογικά στον Ιδιοκτήτη
    if not payments_df.empty:
        payments_df['Date_Obj'] = pd.to_datetime(payments_df['Date_Received'], errors='coerce')
        valid_income = payments_df[
            (payments_df['Date_Obj'].dt.year == selected_year) & 
            (payments_df['Payment_Type'] == 'Ενοίκιο') & 
            (payments_df['Status'].astype(str).str.strip() != 'Εκκρεμεί')
        ]
        
        for _, p in valid_income.iterrows():
            l_id = str(p.get('Lease_ID', ''))
            amt = pd.to_numeric(str(p.get('Amount', '0')).replace(',', '.'), errors='coerce')
            if pd.isna(amt): amt = 0.0
            
            # Βρίσκουμε το ακίνητο
            l_match = leases_df[leases_df['Lease_ID'] == l_id] if not leases_df.empty else pd.DataFrame()
            if not l_match.empty:
                prop_id = str(l_match.iloc[0].get('Property_ID', ''))
                p_match = properties_df[properties_df['Property_ID'] == prop_id] if not properties_df.empty else pd.DataFrame()
                if not p_match.empty:
                    prop = p_match.iloc[0]
                    for i in range(1, 4):
                        afm = str(prop.get(f'AFM_{i}', '')).strip()
                        if len(afm) == 8: afm = "0" + afm
                        name = f"{str(prop.get(f'Name_{i}', '')).strip()} {str(prop.get(f'Surname_{i}', '')).strip()}"
                        right = str(prop.get(f'Right_{i}', '')).strip()
                        perc = pd.to_numeric(str(prop.get(f'Perc_{i}', '0')).replace(',', '.'), errors='coerce')
                        if pd.isna(perc): perc = 0.0
                        
                        if afm and afm != 'nan' and perc > 0 and right in ["Πλήρης Κυριότητα", "Επικαρπία"]:
                            if afm not in owner_finances: owner_finances[afm] = {'Name': name, 'Income': 0, 'ENFIA': 0, 'Prop_Expenses': 0}
                            owner_finances[afm]['Income'] += amt * (perc / 100.0)

    # 2. Υπολογισμός Εξόδων (ΕΝΦΙΑ & Ακινήτου)
    if not expenses_df.empty:
        expenses_df['Date_Obj'] = pd.to_datetime(expenses_df['Date_Paid'], errors='coerce')
        valid_expenses = expenses_df[(expenses_df['Date_Obj'].dt.year == selected_year)]
        
        for _, e in valid_expenses.iterrows():
            amt = pd.to_numeric(str(e.get('Amount', '0')).replace(',', '.'), errors='coerce')
            if pd.isna(amt): amt = 0.0
            cat = str(e.get('Category', ''))
            
            if cat == "ΕΝΦΙΑ":
                afm = str(e.get('AFM', '')).strip()
                if len(afm) == 8: afm = "0" + afm
                if afm in owner_finances: owner_finances[afm]['ENFIA'] += amt
                # Αν πληρώνει ΕΝΦΙΑ αλλά δεν έχει έσοδα, τον προσθέτουμε
                elif afm and afm != 'nan': owner_finances[afm] = {'Name': "Ιδιοκτήτης", 'Income': 0, 'ENFIA': amt, 'Prop_Expenses': 0}
            else:
                # Έξοδο ακινήτου (Ασφάλεια, Ζημιά) - Μοιράζεται βάσει ποσοστού
                prop_id = str(e.get('Property_ID', ''))
                p_match = properties_df[properties_df['Property_ID'] == prop_id] if not properties_df.empty else pd.DataFrame()
                if not p_match.empty:
                    prop = p_match.iloc[0]
                    for i in range(1, 4):
                        afm = str(prop.get(f'AFM_{i}', '')).strip()
                        if len(afm) == 8: afm = "0" + afm
                        right = str(prop.get(f'Right_{i}', '')).strip()
                        perc = pd.to_numeric(str(prop.get(f'Perc_{i}', '0')).replace(',', '.'), errors='coerce')
                        if pd.isna(perc): perc = 0.0
                        
                        # Θεωρούμε ότι τα έξοδα βαρύνουν τον Επικαρπωτή / Πλήρη Κύριο
                        if afm and afm != 'nan' and perc > 0 and right in ["Πλήρης Κυριότητα", "Επικαρπία"]:
                            if afm in owner_finances: owner_finances[afm]['Prop_Expenses'] += amt * (perc / 100.0)

    # 3. Εμφάνιση Αποτελεσμάτων (Οικονομική Ακτινογραφία)
    if not owner_finances:
        st.info("Δεν βρέθηκαν ολοκληρωμένες οικονομικές κινήσεις για το επιλεγμένο έτος.")
    else:
        for afm, data in owner_finances.items():
            inc = data['Income']
            
            # Υπολογισμός Φόρου επί του *Πραγματικού* Εισπραχθέντος
            tax = 0
            if inc <= 12000: tax = inc * 0.15
            elif inc <= 24000: tax = (12000 * 0.15) + ((inc - 12000) * 0.25)
            elif inc <= 35000: tax = (12000 * 0.15) + (12000 * 0.25) + ((inc - 24000) * 0.35)
            else: tax = (12000 * 0.15) + (12000 * 0.25) + (11000 * 0.35) + ((inc - 35000) * 0.45)
            
            enfia = data['ENFIA']
            prop_exp = data['Prop_Expenses']
            net_cash = inc - tax - enfia - prop_exp
            
            color = "success" if net_cash >= 0 else "error"
            st.info(f"**{data['Name']} (ΑΦΜ: {afm})**")
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("1. Εισπράξεις Ενοικίων", f"{inc:,.2f} €".replace('.', ','))
            c2.metric("2. Φόρος Εισοδήματος", f"-{tax:,.2f} €".replace('.', ','))
            c3.metric("3. ΕΝΦΙΑ", f"-{enfia:,.2f} €".replace('.', ','))
            c4.metric("4. Έξοδα / Ζημιές", f"-{prop_exp:,.2f} €".replace('.', ','))
            c5.metric("💰 Καθαρό Ταμείο", f"{net_cash:,.2f} €".replace('.', ','), delta="Κέρδος" if net_cash >=0 else "Ζημιά", delta_color="normal" if net_cash >=0 else "inverse")
            st.divider()

    # --- SECTION 2: ΛΙΣΤΑ ΕΝΕΡΓΩΝ ΜΙΣΘΩΣΕΩΝ ---
    st.subheader("📋 Ενεργές Μισθώσεις")
    if leases_df.empty: st.write("Καμία μίσθωση.")
    else:
        active_leases = []
        today = datetime.today()
        leases_df['End_Date_Obj'] = pd.to_datetime(leases_df['End_Date'], errors='coerce')
        for _, lease in leases_df.iterrows():
            days_rem = (lease['End_Date_Obj'] - today).days if pd.notnull(lease['End_Date_Obj']) else 999
            if days_rem >= 0:
                p_id = str(lease.get('Property_ID', ''))
                p_match = properties_df[properties_df['Property_ID'] == p_id] if not properties_df.empty else pd.DataFrame()
                prop_charact = str(p_match.iloc[0].get('Χαρακτηριστικό', '-')) if not p_match.empty else "-"
                
                safe_rent = pd.to_numeric(str(lease.get('Monthly_Rent', '0')).replace(',', '.'), errors='coerce')
                if pd.isna(safe_rent): safe_rent = 0.0
                active_leases.append({
                    "Ακίνητο": prop_charact,
                    "Λήξη": str(lease['End_Date_Obj'].date()) if pd.notnull(lease['End_Date_Obj']) else "-",
                    "Ημέρες ως Λήξη": days_rem,
                    "Μίσθωμα": f"{safe_rent:.2f} €".replace('.', ',')
                })
        if active_leases: st.write(pd.DataFrame(active_leases).to_html(classes='custom-table', escape=False, index=False, justify='left'), unsafe_allow_html=True)
        else: st.success("Δεν υπάρχουν ενεργές μισθώσεις.")
