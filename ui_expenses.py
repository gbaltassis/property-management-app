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
    st.header("Διαχείριση Εξόδων & Ζημιών")
    
    try:
        properties_df = gsheets_service.fetch_all_properties()
        expenses_df = gsheets_service.fetch_all_expenses()
    except Exception as e:
        st.error(f"Αδυναμία φόρτωσης δεδομένων: {e}")
        return

    # Συγκέντρωση όλων των ΑΦΜ ιδιοκτητών για τον ΕΝΦΙΑ
    owner_afms = set()
    prop_options = {}
    if not properties_df.empty:
        for _, p in properties_df.iterrows():
            prop_options[str(p.get("Property_ID", ""))] = f"{str(p.get('Χαρακτηριστικό', ''))} ({str(p.get('Διεύθυνση', ''))})"
            for i in range(1, 4):
                afm = str(p.get(f'AFM_{i}', '')).strip()
                if len(afm) == 8: afm = "0" + afm
                name = f"{str(p.get(f'Name_{i}', '')).strip()} {str(p.get(f'Surname_{i}', '')).strip()}".strip()
                if afm and afm != 'nan': owner_afms.add(f"{afm} - {name}")

    tab_new, tab_list, tab_edit = st.tabs(["➕ Νέο Έξοδο", "📋 Ιστορικό Εξόδων", "✏️ Επεξεργασία"])

    # --- 1. ΝΕΟ ΕΞΟΔΟ ---
    with tab_new:
        with st.form("new_expense_form", clear_on_submit=True):
            cat_opts = ["ΕΝΦΙΑ", "Ασφάλιση Πυρός", "Ασφάλιση Νομικής Προστασίας", "Ζημιά / Βλάβη", "Άλλο Έξοδο"]
            category = st.selectbox("Κατηγορία Εξόδου *", cat_opts)
            
            st.markdown("---")
            # Δυναμικά πεδία
            afm_sel, prop_sel = "", ""
            if category == "ΕΝΦΙΑ":
                afm_sel = st.selectbox("Ιδιοκτήτης (ΑΦΜ) *", list(owner_afms)) if owner_afms else st.text_input("ΑΦΜ Ιδιοκτήτη *")
            else:
                prop_sel = st.selectbox("Ακίνητο *", list(prop_options.keys()), format_func=lambda x: prop_options[x]) if prop_options else ""

            ec1, ec2 = st.columns(2)
            with ec1: amount = st.text_input("Ποσό (€) *", value="0")
            with ec2: date_paid = st.date_input("Ημ/νία Πληρωμής *", value=date.today())

            desc, ins_comp, ren_date, dur, ins_build, ins_cont = "", "", "", "", "", ""
            
            if category in ["Ζημιά / Βλάβη", "Άλλο Έξοδο"]:
                desc = st.text_area("Περιγραφή (π.χ. Υδραυλικός, Διαρροή) *")
            
            if "Ασφάλιση" in category:
                sc1, sc2, sc3 = st.columns(3)
                with sc1: ins_comp = st.text_input("Ασφαλιστική Εταιρεία *")
                with sc2: ren_date = st.date_input("Ημ/νία Ανανέωσης (Επόμενη) *")
                with sc3: dur = st.selectbox("Διάρκεια Συμβολαίου", ["Ετήσιο", "Εξάμηνο", "Τρίμηνο", "Άλλο"])
                
                if category == "Ασφάλιση Πυρός":
                    st.write("**Ασφαλισμένα Κεφάλαια**")
                    bc1, bc2 = st.columns(2)
                    with bc1: ins_build = st.text_input("Κεφάλαιο Κτιρίου (€)", value="0")
                    with bc2: ins_cont = st.text_input("Κεφάλαιο Περιεχομένου (€)", value="0")

            if st.form_submit_button("Αποθήκευση Εξόδου", type="primary"):
                amt_val = pd.to_numeric(amount.replace(',', '.'), errors='coerce')
                if pd.isna(amt_val) or amt_val <= 0:
                    st.warning("Παρακαλώ εισάγετε έγκυρο ποσό.")
                else:
                    exp_id = f"EXP-{uuid.uuid4().hex[:6].upper()}"
                    final_afm = afm_sel.split(" - ")[0] if " - " in afm_sel else afm_sel
                    r_date_str = ren_date.strftime("%Y-%m-%d") if ren_date else ""
                    
                    row = [exp_id, category, prop_sel, final_afm, amount, date_paid.strftime("%Y-%m-%d"), desc, ins_comp, r_date_str, dur, ins_build, ins_cont]
                    try:
                        gsheets_service.add_expense(row)
                        st.success("Το έξοδο καταχωρήθηκε επιτυχώς!")
                    except Exception as e: st.error(f"Σφάλμα: {e}")

    # --- 2. ΙΣΤΟΡΙΚΟ ---
    with tab_list:
        if expenses_df.empty: st.info("Δεν έχουν καταγραφεί έξοδα.")
        else:
            exp_list = []
            for _, r in expenses_df.iterrows():
                amt = pd.to_numeric(str(r.get('Amount', '0')).replace(',', '.'), errors='coerce')
                if pd.isna(amt): amt = 0.0
                
                cat = str(r.get("Category", ""))
                target = str(r.get("AFM", "")) if cat == "ΕΝΦΙΑ" else prop_options.get(str(r.get("Property_ID", "")), "-")
                
                details = str(r.get("Description", ""))
                if "Ασφάλιση" in cat: details = f"{r.get('Insurance_Company', '')} (Ανανέωση: {r.get('Renewal_Date', '')})"
                
                exp_list.append({
                    "Ημερομηνία": str(r.get("Date_Paid", "")),
                    "Κατηγορία": cat,
                    "Αφορά": target,
                    "Ποσό": f"{amt:.2f} €".replace('.', ','),
                    "Λεπτομέρειες": details
                })
            st.write(pd.DataFrame(exp_list[::-1]).to_html(classes='custom-table', escape=False, index=False, justify='left'), unsafe_allow_html=True)

    # --- 3. ΕΠΕΞΕΡΓΑΣΙΑ / ΔΙΑΓΡΑΦΗ ---
    with tab_edit:
        if expenses_df.empty: st.warning("Δεν υπάρχουν έξοδα.")
        else:
            e_opts = {str(r.get("Expense_ID", "")): f"{r.get('Date_Paid', '')} | {r.get('Category', '')} {r.get('Amount', '')}€" for _, r in expenses_df.iterrows()}
            sel_exp = st.selectbox("Επιλέξτε Έξοδο προς διαγραφή", options=list(e_opts.keys()), format_func=lambda x: e_opts[x])
            if sel_exp:
                if st.button("🗑️ Οριστική Διαγραφή Εξόδου", type="primary"):
                    gsheets_service.delete_expense(sel_exp)
                    st.success("Διαγράφηκε! Ανανεώστε τη σελίδα.")
