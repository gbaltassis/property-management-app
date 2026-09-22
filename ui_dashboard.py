import streamlit as st
import gsheets_service
import pandas as pd
from datetime import datetime
import streamlit.components.v1 as components

# =========================================================================
# ΚΟΙΝΟ CSS & JS ΓΙΑ ΠΑΓΩΜΕΝΟΥΣ HTML ΠΙΝΑΚΕΣ & SORTING
# =========================================================================
COMMON_CSS = """
<style>
    html, body { font-family: sans-serif; }
    .table-container { height: 500px; overflow-y: auto; overflow-x: auto; border: 1px solid #ddd; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 20px; }
    .custom-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 12px; background: white; min-width: 600px; }
    .custom-table th, .custom-table td { padding: 8px 10px; border-bottom: 1px solid #e6e9ef; border-right: 1px solid #e6e9ef; text-align: left; vertical-align: middle; line-height: 1.2; }
    .custom-table th { background-color: #f0f2f6; color: #31333F; position: sticky; top: 0; z-index: 4; box-shadow: 0 1px 0 #ddd; cursor: pointer; user-select: none; transition: background-color 0.2s;}
    .custom-table th:hover { background-color: #e2e6ea; }
    .custom-table th:first-child, .custom-table td:first-child { position: sticky; left: 0; z-index: 3; background-color: #ffffff; box-shadow: 1px 0 0 #ddd; font-weight: 600; min-width: 100px; max-width: 160px; white-space: normal !important; word-wrap: break-word; }
    .custom-table th:first-child { z-index: 5; background-color: #f0f2f6; box-shadow: 1px 1px 0 #ddd; }
    
    @media (prefers-color-scheme: dark) {
        .table-container { border-color: #444; }
        .custom-table { background: #0e1117; color: white; }
        .custom-table th { background-color: #262730; color: white; box-shadow: 0 1px 0 #444; }
        .custom-table th:hover { background-color: #383a45; }
        .custom-table th:first-child, .custom-table td:first-child { background-color: #0e1117; box-shadow: 1px 0 0 #666; color: white; }
        .custom-table th:first-child { background-color: #262730; box-shadow: 1px 1px 0 #666; }
        .custom-table td { border-color: #444; }
    }
</style>
"""

COMMON_JS = """
<script>
    function sortTable(tableId, n) {
        var table, rows, switching, i, x, y, shouldSwitch, dir, switchcount = 0;
        table = document.getElementById(tableId);
        switching = true; dir = "asc"; 
        while (switching) {
            switching = false; rows = table.getElementsByTagName("TR");
            for (i = 1; i < (rows.length - 1); i++) {
                shouldSwitch = false;
                x = rows[i].getElementsByTagName("TD")[n]; y = rows[i + 1].getElementsByTagName("TD")[n];
                if(!x || !y) continue;
                let valX = x.innerText.trim().toLowerCase(); let valY = y.innerText.trim().toLowerCase();
                if(valX.includes('€')) valX = parseFloat(valX.replace(/[^0-9,-]/g, '').replace(',', '.'));
                if(valY.includes('€')) valY = parseFloat(valY.replace(/[^0-9,-]/g, '').replace(',', '.'));
                if(valX.match(/^\\d{4}-\\d{2}-\\d{2}/)) valX = new Date(valX).getTime();
                if(valY.match(/^\\d{4}-\\d{2}-\\d{2}/)) valY = new Date(valY).getTime();
                
                // Ειδικός κανόνας για τον αριθμό ημερών στη στήλη "Ημέρες ως Λήξη"
                if(!isNaN(valX) && !isNaN(valY) && valX !== "" && valY !== "") {
                    valX = parseFloat(valX);
                    valY = parseFloat(valY);
                }

                if (dir == "asc") { if (valX > valY) { shouldSwitch = true; break; } } 
                else if (dir == "desc") { if (valX < valY) { shouldSwitch = true; break; } }
            }
            if (shouldSwitch) { rows[i].parentNode.insertBefore(rows[i + 1], rows[i]); switching = true; switchcount ++; } 
            else { if (switchcount == 0 && dir == "asc") { dir = "desc"; switching = true; } }
        }
    }
</script>
"""

def calculate_property_tax(gross_income):
    if gross_income <= 0: return 0.0
    taxable = gross_income * 0.95
    tax = 0.0
    if taxable > 36000:
        tax += (taxable - 36000) * 0.45
        taxable = 36000
    if taxable > 24000:
        tax += (taxable - 24000) * 0.35
        taxable = 24000
    if taxable > 12000:
        tax += (taxable - 12000) * 0.25
        taxable = 12000
    if taxable > 0:
        tax += taxable * 0.15
    return tax

def show():
    st.markdown(COMMON_CSS, unsafe_allow_html=True)
    st.header("Επισκόπηση & Ταμειακές Ροές")
    
    try:
        leases_df = gsheets_service.fetch_all_leases()
        properties_df = gsheets_service.fetch_all_properties()
        payments_df = gsheets_service.fetch_all_payments()
        try: expenses_df = gsheets_service.fetch_all_expenses()
        except: expenses_df = pd.DataFrame() 
    except Exception as e:
        st.error(f"Αδυναμία φόρτωσης δεδομένων: {e}")
        return

    # --- SECTION 1: ΠΡΑΓΜΑΤΙΚΕΣ ΤΑΜΕΙΑΚΕΣ ΡΟΕΣ (CASH FLOW) ---
    st.subheader("💡 Πραγματικές Ταμειακές Ροές ανά Ιδιοκτήτη")
    current_year = datetime.today().year
    selected_year = st.selectbox("Ανάλυση Έτους:", [current_year - 1, current_year, current_year + 1], index=1)
    
    owner_finances = {} 

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
                elif afm and afm != 'nan': owner_finances[afm] = {'Name': "Ιδιοκτήτης", 'Income': 0, 'ENFIA': amt, 'Prop_Expenses': 0}
            else:
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
                        
                        if afm and afm != 'nan' and perc > 0 and right in ["Πλήρης Κυριότητα", "Επικαρπία"]:
                            if afm in owner_finances: owner_finances[afm]['Prop_Expenses'] += amt * (perc / 100.0)

    # 3. Εμφάνιση Αποτελεσμάτων
    if not owner_finances:
        st.info("Δεν βρέθηκαν ολοκληρωμένες οικονομικές κινήσεις για το επιλεγμένο έτος.")
    else:
        for afm, data in owner_finances.items():
            inc = data['Income']
            tax = calculate_property_tax(inc) # Χρήση της σωστής μαθηματικής συνάρτησης
            
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
                
        if not active_leases:
            st.success("Δεν υπάρχουν ενεργές μισθώσεις.")
        else:
            # HTML Παγωμένος Πίνακας Dashboard
            html_code = f"""
            <!DOCTYPE html><html><head><style>{COMMON_CSS}</style></head><body>
            <div class="table-container">
                <table id="dash-lease-table" class="custom-table">
                    <thead>
                        <tr>
                            <th onclick="sortTable('dash-lease-table', 0)">Ακίνητο ⇕</th>
                            <th onclick="sortTable('dash-lease-table', 1)">Λήξη ⇕</th>
                            <th onclick="sortTable('dash-lease-table', 2)">Ημέρες ως Λήξη ⇕</th>
                            <th onclick="sortTable('dash-lease-table', 3)">Μίσθωμα ⇕</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            for item in active_leases:
                # Χρωματισμός των ημερών αν είναι λιγότερες από 60
                rem_color = "color: #dc3545; font-weight: bold;" if item['Ημέρες ως Λήξη'] <= 60 else ""
                html_code += f"""
                        <tr>
                            <td>{item['Ακίνητο']}</td>
                            <td>{item['Λήξη']}</td>
                            <td style="{rem_color}">{item['Ημέρες ως Λήξη']}</td>
                            <td><strong>{item['Μίσθωμα']}</strong></td>
                        </tr>
                """
            html_code += f"""
                    </tbody>
                </table>
            </div>
            {COMMON_JS}
            </body></html>
            """
            t_height = min(550, 150 + len(active_leases) * 45)
            components.html(html_code, height=t_height, scrolling=False)
