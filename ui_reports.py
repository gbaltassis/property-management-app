import streamlit as st
import pandas as pd
import gsheets_service
from datetime import date, datetime
import calendar
import json

COMMON_CSS = """
<style>
    .metric-card {
        background-color: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px; padding: 15px; text-align: center; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .metric-title { font-size: 14px; color: #6c757d; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }
    .metric-value { font-size: 24px; color: #31333F; font-weight: 700; }
    .metric-sub { font-size: 12px; color: #adb5bd; margin-top: 5px; }
    .val-positive { color: #28a745 !important; }
    .val-negative { color: #dc3545 !important; }
    
    /* CSS ΓΙΑ ΠΑΓΩΜΕΝΕΣ ΕΠΙΚΕΦΑΛΙΔΕΣ ΚΑΙ ΠΡΩΤΗ ΣΤΗΛΗ ΣΕ HTML ΠΙΝΑΚΕΣ */
    .table-container {
        max-height: 500px;
        overflow-y: auto;
        overflow-x: auto;
        border: 1px solid #ddd;
        border-radius: 8px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .custom-table { width: 100%; border-collapse: separate; border-spacing: 0; font-family: sans-serif; font-size: 13px; background: white; min-width: 1000px; }
    .custom-table th, .custom-table td { padding: 10px; border-bottom: 1px solid #e6e9ef; border-right: 1px solid #e6e9ef; text-align: right; vertical-align: top; }
    .custom-table th { background-color: #f0f2f6; color: #31333F; position: sticky; top: 0; z-index: 2; box-shadow: 0 1px 0 #ddd; text-align: center;}
    .custom-table th:first-child, .custom-table td:first-child { position: sticky; left: 0; z-index: 1; background-color: #ffffff; box-shadow: 1px 0 0 #ddd; font-weight: 600; min-width: 180px; text-align: left; }
    .custom-table th:first-child { z-index: 3; background-color: #f0f2f6; box-shadow: 1px 1px 0 #ddd; }
    
    @media (prefers-color-scheme: dark) {
        .table-container { border-color: #444; }
        .custom-table { background: #0e1117; color: white; }
        .custom-table th { background-color: #262730; color: white; box-shadow: 0 1px 0 #444; }
        .custom-table th:first-child, .custom-table td:first-child { background-color: #0e1117; box-shadow: 1px 0 0 #666; color: white; }
        .custom-table th:first-child { background-color: #262730; box-shadow: 1px 1px 0 #666; }
        .custom-table td { border-color: #444; }
    }
</style>
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
    st.header("Οικονομικές Αναφορές & Cash Flow")
    st.caption("Σύγκριση Θεωρητικής vs Πραγματικής Απόδοσης ανά Ιδιοκτήτη (με υπολογισμό Φόρων και ΕΝΦΙΑ).")

    try:
        props_df = gsheets_service.fetch_all_properties()
        leases_df = gsheets_service.fetch_all_leases()
        payments_df = gsheets_service.fetch_all_payments()
        expenses_df = gsheets_service.fetch_all_expenses()
        insurances_df = gsheets_service.fetch_all_insurances()
    except Exception as e:
        st.error(f"Αδυναμία φόρτωσης δεδομένων: {e}")
        return

    if props_df.empty:
        st.info("Δεν υπάρχουν ακίνητα.")
        return

    owners_dict = {}
    for _, p in props_df.iterrows():
        for i in range(1, 4):
            afm = str(p.get(f'AFM_{i}', '')).strip()
            if len(afm) == 8: afm = "0" + afm
            name = f"{str(p.get(f'Name_{i}', '')).strip()} {str(p.get(f'Surname_{i}', '')).strip()}".strip()
            if afm and afm != 'nan': owners_dict[afm] = name

    if not owners_dict:
        st.warning("Δεν βρέθηκαν καταχωρημένοι ιδιοκτήτες στα ακίνητα.")
        return

    col1, col2 = st.columns(2)
    with col1:
        current_year = datetime.today().year
        year_opts = list(range(current_year - 2, current_year + 3))
        selected_year = st.selectbox("Επιλογή Έτους", year_opts, index=year_opts.index(current_year), key="rep_year_filter")
    with col2:
        afm_opts = list(owners_dict.keys())
        selected_afm = st.selectbox("Επιλογή Ιδιοκτήτη (ΑΦΜ)", afm_opts, format_func=lambda x: f"{x} - {owners_dict[x]}", key="rep_afm_filter")
    st.markdown("---")

    owner_props = []
    total_owner_prop_value = 0.0
    
    for _, p in props_df.iterrows():
        ownership_perc = 0.0
        for i in range(1, 4):
            afm = str(p.get(f'AFM_{i}', '')).strip()
            if len(afm) == 8: afm = "0" + afm
            if afm == selected_afm:
                perc = pd.to_numeric(str(p.get(f'Perc_{i}', '0')).replace(',', '.'), errors='coerce')
                if pd.notna(perc): ownership_perc += perc
        
        if ownership_perc > 0:
            p_val = pd.to_numeric(str(p.get('Property_Value', '0')).replace(',', '.'), errors='coerce')
            if pd.isna(p_val): p_val = 0.0
            
            fixed_exp = pd.to_numeric(str(p.get('Fixed_Yearly_Expenses', '0')).replace(',', '.'), errors='coerce')
            if pd.isna(fixed_exp): fixed_exp = 0.0
            
            owner_share_value = p_val * (ownership_perc / 100)
            total_owner_prop_value += owner_share_value
            
            owner_props.append({
                "Property_ID": str(p.get('Property_ID', '')),
                "Name": str(p.get('Χαρακτηριστικό', '-')),
                "Perc": ownership_perc / 100,
                "Owner_Share_Value": owner_share_value,
                "Fixed_Exp_100": fixed_exp
            })

    if not owner_props:
        st.info("Ο επιλεγμένος ιδιοκτήτης δεν έχει ποσοστό σε κανένα ακίνητο.")
        return

    total_surcharge = 0.0
    enfia_breakdown_year = {}
    
    if not expenses_df.empty:
        enfia_rows = expenses_df[(expenses_df["Category"] == "ΕΝΦΙΑ") & (expenses_df["AFM"] == selected_afm)]
        for _, er in enfia_rows.iterrows():
            try: d_paid = datetime.strptime(str(er.get("Date_Paid", "")), "%Y-%m-%d").date()
            except: continue
            if d_paid.year == selected_year:
                sur = pd.to_numeric(str(er.get("ENFIA_Surcharge", "0")).replace(',', '.'), errors='coerce')
                if pd.notna(sur): total_surcharge += sur
                
                b_str = str(er.get("ENFIA_Breakdown", "{}")).replace('nan', '{}')
                try: b_dict = json.loads(b_str)
                except: b_dict = {}
                
                for k, v in b_dict.items():
                    enfia_breakdown_year[k] = enfia_breakdown_year.get(k, 0.0) + v

    results = []
    total_exp_income, total_act_income = 0.0, 0.0
    
    for op in owner_props:
        pid = op["Property_ID"]
        perc = op["Perc"]
        
        exp_income = 0.0
        prop_leases = leases_df[leases_df["Property_ID"] == pid] if not leases_df.empty else pd.DataFrame()
        for m in range(1, 13):
            last_day = calendar.monthrange(selected_year, m)[1]
            month_end = date(selected_year, m, last_day)
            month_start = date(selected_year, m, 1)
            
            for _, l in prop_leases.iterrows():
                try: s_date = datetime.strptime(str(l['Start_Date']), "%Y-%m-%d").date()
                except: continue
                try: e_date = datetime.strptime(str(l['End_Date']), "%Y-%m-%d").date()
                except: e_date = date(2099, 12, 31)
                
                if s_date <= month_end and e_date >= month_start:
                    rent = pd.to_numeric(str(l.get('Monthly_Rent', '0')).replace(',', '.'), errors='coerce')
                    if pd.notna(rent): exp_income += (rent * perc)
                    break 

        act_income = 0.0
        if not payments_df.empty and not prop_leases.empty:
            l_ids = prop_leases["Lease_ID"].tolist()
            pay_rows = payments_df[(payments_df["Lease_ID"].isin(l_ids)) & (payments_df["Payment_Type"] == "Ενοίκιο") & (payments_df["Status"] == "Εξοφλήθηκε")]
            for _, pr in pay_rows.iterrows():
                try: pay_d = datetime.strptime(str(pr.get("Date_Received", "")), "%Y-%m-%d").date()
                except: continue
                if pay_d.year == selected_year:
                    amt = pd.to_numeric(str(pr.get("Amount", "0")).replace(',', '.'), errors='coerce')
                    if pd.notna(amt): act_income += (amt * perc)

        exp_ins = 0.0
        if not insurances_df.empty:
            ins_rows = insurances_df[insurances_df["Property_ID"] == pid]
            for _, ir in ins_rows.iterrows():
                prem = pd.to_numeric(str(ir.get("Premium", "0")).replace(',', '.'), errors='coerce')
                if pd.notna(prem): exp_ins += (prem * perc)
                
        allocated_surcharge = 0.0
        if total_owner_prop_value > 0:
            allocated_surcharge = (op["Owner_Share_Value"] / total_owner_prop_value) * total_surcharge
        
        prop_main_enfia = enfia_breakdown_year.get(pid, 0.0)
        total_enfia = prop_main_enfia + allocated_surcharge
        
        expected_expenses = (op["Fixed_Exp_100"] * perc) + exp_ins + total_enfia

        act_exp_other = 0.0
        if not expenses_df.empty:
            exp_rows = expenses_df[(expenses_df["Property_ID"] == pid) & (expenses_df["Category"] != "ΕΝΦΙΑ")]
            for _, exr in exp_rows.iterrows():
                try: ex_d = datetime.strptime(str(exr.get("Date_Paid", "")), "%Y-%m-%d").date()
                except: continue
                if ex_d.year == selected_year:
                    ex_amt = pd.to_numeric(str(exr.get("Amount", "0")).replace(',', '.'), errors='coerce')
                    if pd.notna(ex_amt): act_exp_other += (ex_amt * perc)
        
        actual_expenses = act_exp_other + total_enfia 

        total_exp_income += exp_income
        total_act_income += act_income

        results.append({
            "Property_ID": pid,
            "Name": op["Name"],
            "Perc": perc,
            "Exp_Income": exp_income,
            "Act_Income": act_income,
            "Exp_Expenses": expected_expenses,
            "Act_Expenses": actual_expenses
        })

    total_exp_tax = calculate_property_tax(total_exp_income)
    total_act_tax = calculate_property_tax(total_act_income)

    final_results = []
    total_exp_net, total_act_net = 0.0, 0.0

    for r in results:
        prop_exp_tax = total_exp_tax * (r["Exp_Income"] / total_exp_income) if total_exp_income > 0 else 0.0
        prop_act_tax = total_act_tax * (r["Act_Income"] / total_act_income) if total_act_income > 0 else 0.0
        
        exp_net = r["Exp_Income"] - r["Exp_Expenses"] - prop_exp_tax
        act_net = r["Act_Income"] - r["Act_Expenses"] - prop_act_tax
        
        total_exp_net += exp_net
        total_act_net += act_net
        
        final_results.append({
            "Ακίνητο": f"{r['Name']} ({r['Perc']*100:.0f}%)",
            "Θεωρ. Έσοδα": f"{r['Exp_Income']:.2f} €",
            "Πραγμ. Έσοδα": f"{r['Act_Income']:.2f} €",
            "Θεωρ. Έξοδα<br><span style='font-size:10px;'>(+ΕΝΦΙΑ)</span>": f"{r['Exp_Expenses']:.2f} €",
            "Πραγμ. Έξοδα<br><span style='font-size:10px;'>(+ΕΝΦΙΑ)</span>": f"{r['Act_Expenses']:.2f} €",
            "Θεωρ. Φόρος": f"{prop_exp_tax:.2f} €",
            "Πραγμ. Φόρος": f"{prop_act_tax:.2f} €",
            "Θεωρ. Καθαρό": f"{exp_net:.2f} €",
            "Πραγμ. Καθαρό": f"{act_net:.2f} €",
            "Απόκλιση": f"{(act_net - exp_net):.2f} €"
        })

    st.markdown(f"#### Συνολική Εικόνα ({selected_year}) - ΑΦΜ: {selected_afm}")
    
    mc1, mc2, mc3, mc4 = st.columns(4)
    with mc1:
        st.markdown(f"<div class='metric-card'><div class='metric-title'>Συνολικά Έσοδα</div><div class='metric-value'>{total_act_income:.2f} €</div><div class='metric-sub'>Θεωρητικά: {total_exp_income:.2f} €</div></div>", unsafe_allow_html=True)
    with mc2:
        st.markdown(f"<div class='metric-card'><div class='metric-title'>Συνολικός Φόρος</div><div class='metric-value val-negative'>-{total_act_tax:.2f} €</div><div class='metric-sub'>Θεωρητικός: -{total_exp_tax:.2f} €</div></div>", unsafe_allow_html=True)
    with mc3:
        st.markdown(f"<div class='metric-card'><div class='metric-title'>Καθαρό Κέρδος</div><div class='metric-value val-positive'>{total_act_net:.2f} €</div><div class='metric-sub'>Θεωρητικό: {total_exp_net:.2f} €</div></div>", unsafe_allow_html=True)
    with mc4:
        variance = total_act_net - total_exp_net
        var_color = "val-positive" if variance >= 0 else "val-negative"
        sign = "+" if variance >= 0 else ""
        st.markdown(f"<div class='metric-card'><div class='metric-title'>Απόκλιση (Variance)</div><div class='metric-value {var_color}'>{sign}{variance:.2f} €</div><div class='metric-sub'>Σε σχέση με το προσδοκώμενο</div></div>", unsafe_allow_html=True)

    st.markdown("#### Ανάλυση ανά Ακίνητο")
    df_results = pd.DataFrame(final_results)
    
    def highlight_variance(val):
        if "€" in val and " " in val:
            try:
                num = float(val.replace(" €", "").replace(",", "."))
                if num < 0: return 'color: #dc3545; font-weight: bold;'
                elif num > 0: return 'color: #28a745; font-weight: bold;'
            except: pass
        return ''

    # ΠΑΓΩΜΕΝΟΣ HTML ΠΙΝΑΚΑΣ ΓΙΑ ΤΙΣ ΑΝΑΦΟΡΕΣ (ΜΕ STYLER HTML OUTPUT)
    html_table = df_results.style.applymap(highlight_variance, subset=['Απόκλιση']).to_html(classes='custom-table', escape=False, index=False)
    st.write(f'<div class="table-container">{html_table}</div>', unsafe_allow_html=True)
