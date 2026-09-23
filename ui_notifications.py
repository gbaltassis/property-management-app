import streamlit as st
import pandas as pd
import gsheets_service
from datetime import datetime, date
import uuid
import urllib.parse
import time

COMMON_CSS = """
<style>
    .notif-card { background-color: #ffffff; border-left: 5px solid #007bff; border-radius: 6px; padding: 15px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .notif-warning { border-left-color: #ffc107; }
    .notif-danger { border-left-color: #dc3545; }
    .notif-debt { border-left-color: #fd7e14; }
    .notif-custom { border-left-color: #17a2b8; }
    .notif-title { font-size: 16px; font-weight: bold; color: #31333F; margin-bottom: 5px; }
    .notif-text { font-size: 13px; color: #555; margin-bottom: 10px; background-color: #f8f9fa; padding: 10px; border-radius: 4px; white-space: pre-wrap; }
    .notif-meta { font-size: 11px; color: #888; margin-bottom: 10px; }
    .link-btn { display: inline-block; padding: 6px 12px; margin-right: 5px; margin-bottom: 5px; border-radius: 4px; text-decoration: none; font-size: 12px; font-weight: bold; color: white !important; text-align: center; cursor: pointer; transition: opacity 0.2s; }
    .link-btn:hover { opacity: 0.8; }
    .btn-sms { background-color: #28a745; }
    .btn-viber { background-color: #665CAC; }
    .btn-email { background-color: #ea4335; }
</style>
"""

def show():
    if "custom_notif_mode" not in st.session_state:
        st.session_state.custom_notif_mode = False

    st.markdown(COMMON_CSS, unsafe_allow_html=True)
    
    col_t, col_b = st.columns([3, 1])
    col_t.header("🔔 Κέντρο Ειδοποιήσεων")
    if not st.session_state.custom_notif_mode:
        if col_b.button("➕ Νέο Μήνυμα", use_container_width=True):
            st.session_state.custom_notif_mode = True
            st.rerun()

    try:
        leases_df = gsheets_service.fetch_all_leases()
        insurances_df = gsheets_service.fetch_all_insurances()
        properties_df = gsheets_service.fetch_all_properties()
        tenants_df = gsheets_service.fetch_all_tenants()
        payments_df = gsheets_service.fetch_all_payments()
        
        try: notif_df = gsheets_service.fetch_all_notifications()
        except: notif_df = pd.DataFrame(columns=["Log_ID", "Date_Sent", "Target", "Type", "Message"])
    except Exception as e:
        st.error(f"Αδυναμία φόρτωσης δεδομένων: {e}")
        return

    today = date.today()
    pending_notifications = []

    # =====================================================================
    # ΛΕΙΤΟΥΡΓΙΑ 1: ΧΕΙΡΟΚΙΝΗΤΗ ΔΗΜΙΟΥΡΓΙΑ ΕΙΔΟΠΟΙΗΣΗΣ (CUSTOM)
    # =====================================================================
    if st.session_state.custom_notif_mode:
        st.markdown("### ✍️ Σύνταξη Νέου Μηνύματος")
        if st.button("⬅️ Ακύρωση", key="cancel_custom"):
            st.session_state.custom_notif_mode = False
            st.rerun()
            
        with st.form("custom_message_form"):
            c_target_type = st.radio("Προς ποιον θέλετε να στείλετε;", ["Ενοικιαστή", "Ιδιοκτήτη"], horizontal=True)
            
            target_opts = {}
            if c_target_type == "Ενοικιαστή" and not tenants_df.empty:
                for _, t in tenants_df.iterrows():
                    target_opts[str(t.get("Tenant_ID", ""))] = {
                        "name": f"{t.get('Επώνυμο', '')} {t.get('Όνομα', '')}".strip(),
                        "phone": str(t.get('Κινητό', '')).replace('nan', ''),
                        "email": str(t.get('Email', '')).replace('nan', '')
                    }
            elif c_target_type == "Ιδιοκτήτη" and not properties_df.empty:
                for _, p in properties_df.iterrows():
                    for i in range(1, 4):
                        n, s, afm = str(p.get(f'Name_{i}', '')), str(p.get(f'Surname_{i}', '')), str(p.get(f'AFM_{i}', ''))
                        if n and n != 'nan':
                            target_opts[afm] = {
                                "name": f"{n} {s}".strip(),
                                "phone": "", # Δεν έχουμε πεδίο τηλεφώνου ιδιοκτήτη στο Μητρώο, θα το βάζει manual
                                "email": ""
                            }
                            
            t_keys = list(target_opts.keys())
            sel_target_id = st.selectbox("Επιλέξτε Παραλήπτη", t_keys, format_func=lambda x: target_opts[x]['name']) if t_keys else None
            
            c_msg = st.text_area("Κείμενο Μηνύματος", placeholder="Γράψτε εδώ το μήνυμά σας...")
            
            if st.form_submit_button("✅ Δημιουργία Μηνύματος (Links)", type="primary"):
                if not c_msg or not sel_target_id:
                    st.warning("Παρακαλώ επιλέξτε παραλήπτη και γράψτε κείμενο.")
                else:
                    t_info = target_opts[sel_target_id]
                    encoded_msg = urllib.parse.quote(c_msg)
                    clean_phone = t_info['phone'].replace(' ', '')
                    if clean_phone and not clean_phone.startswith('+30'): clean_phone = f"+30{clean_phone}"
                    
                    sms_link = f"sms:{clean_phone}?body={encoded_msg}" if clean_phone else f"sms:?body={encoded_msg}"
                    viber_link = f"viber://chat?number={clean_phone}" if clean_phone else "#"
                    email_link = f"mailto:{t_info['email']}?subject=Ενημέρωση από Property Management&body={encoded_msg}" if t_info['email'] else "#"
                    
                    st.success("Το μήνυμα δημιουργήθηκε! Επιλέξτε τρόπο αποστολής:")
                    st.markdown(f"""
                        <div class="notif-card notif-custom">
                            <div class="notif-title">✉️ Προσαρμοσμένο Μήνυμα</div>
                            <div class="notif-meta">📍 Παραλήπτης: <b>{t_info['name']}</b> | 📞 {t_info['phone'] or '---'} | ✉️ {t_info['email'] or '---'}</div>
                            <div class="notif-text">{c_msg}</div>
                            <div>
                                <a href="{sms_link}" class="link-btn btn-sms" target="_blank">📱 Αποστολή SMS</a>
                                <a href="{viber_link}" class="link-btn btn-viber" target="_blank">💜 Άνοιγμα Viber</a>
                                <a href="{email_link}" class="link-btn btn-email" target="_blank">📧 Αποστολή Email</a>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    st.stop() # Σταματάει εδώ για να μην δείξει τα αυτόματα από κάτω
        return

    # =====================================================================
    # ΛΕΙΤΟΥΡΓΙΑ 2: ΑΥΤΟΜΑΤΟΣ ΕΛΕΓΧΟΣ ΟΦΕΙΛΩΝ (ΕΝΟΙΚΙΑΣΤΕΣ)
    # =====================================================================
    if not payments_df.empty:
        pending_payments = payments_df[payments_df['Status'] == 'Εκκρεμεί']
        for _, pay in pending_payments.iterrows():
            pay_id = str(pay.get("Payment_ID", ""))
            l_id = str(pay.get("Lease_ID", ""))
            p_type = str(pay.get("Payment_Type", ""))
            amt = pd.to_numeric(str(pay.get("Amount", "0")).replace(',', '.'), errors='coerce')
            if pd.isna(amt): amt = 0.0
            
            notif_type = f"DEBT_{pay_id}"
            if not notif_df.empty and not notif_df[notif_df["Type"] == notif_type].empty:
                continue # Το έχουμε ήδη στείλει
                
            l_match = leases_df[leases_df['Lease_ID'] == l_id] if not leases_df.empty else pd.DataFrame()
            if not l_match.empty:
                t_ids = [t.strip() for t in str(l_match.iloc[0].get("Tenant_ID", "")).split(',') if t.strip()]
                tenant_name, tenant_phone, tenant_email = "Ενοικιαστή", "", ""
                if t_ids and not tenants_df.empty:
                    t_match = tenants_df[tenants_df["Tenant_ID"] == t_ids[0]]
                    if not t_match.empty:
                        tenant_name = f"{str(t_match.iloc[0].get('Επώνυμο', ''))} {str(t_match.iloc[0].get('Όνομα', ''))}".strip()
                        tenant_phone = str(t_match.iloc[0].get('Κινητό', '')).replace('nan', '')
                        tenant_email = str(t_match.iloc[0].get('Email', '')).replace('nan', '')
                
                m_str = str(pay.get("Calc_Month", ""))
                y_str = str(pay.get("Calc_Year", ""))
                period = f"του {m_str}/{y_str}" if m_str != "0" else "που έχει καταχωρηθεί"
                
                msg = (f"Αγαπητέ/ή {tenant_name},\n\n"
                       f"Σας υπενθυμίζουμε ότι υπάρχει μια εκκρεμής οφειλή {amt:.2f}€ "
                       f"για {p_type} ({period}).\n\n"
                       f"Παρακαλούμε μεριμνήστε για την τακτοποίησή της.\nΜε εκτίμηση.")
                
                pending_notifications.append({
                    "title": f"💰 Εκκρεμής Οφειλή ({p_type}: {amt:.2f}€)",
                    "target_name": tenant_name,
                    "target_phone": tenant_phone,
                    "target_email": tenant_email,
                    "message": msg,
                    "type": notif_type,
                    "css_class": "notif-debt",
                    "entity": f"Λογαριασμός / Ενοίκιο"
                })

    # =====================================================================
    # ΛΕΙΤΟΥΡΓΙΑ 3: ΕΛΕΓΧΟΣ ΑΣΦΑΛΙΣΤΗΡΙΩΝ (15, 7, 2 ΜΕΡΕΣ ΠΡΙΝ)
    # =====================================================================
    if not insurances_df.empty:
        for _, ins in insurances_df.iterrows():
            try: ren_d = datetime.strptime(str(ins.get("Renewal_Date", "")), "%Y-%m-%d").date()
            except: continue
            
            days_left = (ren_d - today).days
            
            if days_left in [15, 7, 2]:
                i_id = str(ins.get("Insurance_ID", ""))
                p_id = str(ins.get("Property_ID", ""))
                comp = str(ins.get("Company", ""))
                
                p_match = properties_df[properties_df["Property_ID"] == p_id] if not properties_df.empty else pd.DataFrame()
                owner_name, prop_charact = "Ιδιοκτήτη", "Ακίνητο"
                if not p_match.empty:
                    prop_charact = str(p_match.iloc[0].get("Χαρακτηριστικό", "Ακίνητο"))
                    owner_name = f"{str(p_match.iloc[0].get('Name_1', ''))} {str(p_match.iloc[0].get('Surname_1', ''))}".strip()

                notif_type = f"INS_{days_left}_{i_id}"
                
                if not notif_df.empty and not notif_df[notif_df["Type"] == notif_type].empty: continue
                
                msg = (f"Γεια σας {owner_name},\n\n"
                       f"Υπενθύμιση: Το ασφαλιστήριο συμβόλαιο για το ακίνητο '{prop_charact}' "
                       f"στην εταιρεία {comp} λήγει σε {days_left} ημέρες ({ren_d.strftime('%d/%m/%Y')}).\n\n"
                       f"Παρακαλώ μεριμνήστε για την ανανέωσή του.\nΜε εκτίμηση.")
                
                urgency_class = "notif-danger" if days_left == 2 else ("notif-warning" if days_left == 7 else "")
                
                pending_notifications.append({
                    "title": f"🛡️ Λήξη Ασφαλιστηρίου σε {days_left} μέρες",
                    "target_name": owner_name,
                    "target_phone": "", 
                    "target_email": "",
                    "message": msg,
                    "type": notif_type,
                    "css_class": urgency_class,
                    "entity": prop_charact
                })

    # =====================================================================
    # ΛΕΙΤΟΥΡΓΙΑ 4: ΕΛΕΓΧΟΣ ΜΙΣΘΩΣΕΩΝ (30, 10 ΜΕΡΕΣ ΠΡΙΝ)
    # =====================================================================
    if not leases_df.empty:
        for _, lease in leases_df.iterrows():
            try: end_d = datetime.strptime(str(lease.get("End_Date", "")), "%Y-%m-%d").date()
            except: continue
            
            days_left = (end_d - today).days
            
            if days_left in [30, 10]:
                l_id = str(lease.get("Lease_ID", ""))
                p_id = str(lease.get("Property_ID", ""))
                t_ids = [t.strip() for t in str(lease.get("Tenant_ID", "")).split(',') if t.strip()]
                
                p_match = properties_df[properties_df["Property_ID"] == p_id] if not properties_df.empty else pd.DataFrame()
                prop_charact = str(p_match.iloc[0].get("Χαρακτηριστικό", "Ακίνητο")) if not p_match.empty else "Ακίνητο"
                
                tenant_name, tenant_phone, tenant_email = "Ενοικιαστή", "", ""
                if t_ids and not tenants_df.empty:
                    t_match = tenants_df[tenants_df["Tenant_ID"] == t_ids[0]]
                    if not t_match.empty:
                        tenant_name = f"{str(t_match.iloc[0].get('Επώνυμο', ''))} {str(t_match.iloc[0].get('Όνομα', ''))}".strip()
                        tenant_phone = str(t_match.iloc[0].get('Κινητό', '')).replace('nan', '')
                        tenant_email = str(t_match.iloc[0].get('Email', '')).replace('nan', '')

                notif_type = f"LEASE_{days_left}_{l_id}"
                
                if not notif_df.empty and not notif_df[notif_df["Type"] == notif_type].empty: continue
                
                msg = (f"Αγαπητέ/ή {tenant_name},\n\n"
                       f"Σας ενημερώνουμε ότι το μισθωτήριο συμβόλαιο για το ακίνητο '{prop_charact}' "
                       f"λήγει σε {days_left} ημέρες ({end_d.strftime('%d/%m/%Y')}).\n\n"
                       f"Παρακαλούμε επικοινωνήστε μαζί μας το συντομότερο για να συζητήσουμε "
                       f"τις προθέσεις σας σχετικά με την ανανέωση.\nΜε εκτίμηση.")
                
                urgency_class = "notif-warning" if days_left == 10 else ""
                
                pending_notifications.append({
                    "title": f"📝 Λήξη Μίσθωσης σε {days_left} μέρες",
                    "target_name": tenant_name,
                    "target_phone": tenant_phone,
                    "target_email": tenant_email,
                    "message": msg,
                    "type": notif_type,
                    "css_class": urgency_class,
                    "entity": prop_charact
                })

    # --- ΕΜΦΑΝΙΣΗ ΑΥΤΟΜΑΤΩΝ ΕΙΔΟΠΟΙΗΣΕΩΝ ΣΤΟ UI ---
    if not pending_notifications:
        st.success("🎉 Δεν υπάρχουν εκκρεμείς αυτόματες ειδοποιήσεις για σήμερα!")
        return

    st.write(f"Βρέθηκαν **{len(pending_notifications)}** αυτόματες εκκρεμότητες:")

    for notif in pending_notifications:
        encoded_msg = urllib.parse.quote(notif["message"])
        
        clean_phone = str(notif["target_phone"]).replace(' ', '')
        if clean_phone and not clean_phone.startswith('+30'): clean_phone = f"+30{clean_phone}"

        sms_link = f"sms:{clean_phone}?body={encoded_msg}" if clean_phone else f"sms:?body={encoded_msg}"
        viber_link = f"viber://chat?number={clean_phone}" if clean_phone else "#"
        email_link = f"mailto:{notif['target_email']}?subject=Ενημέρωση από Property Management&body={encoded_msg}" if notif["target_email"] else "#"

        st.markdown(f"""
            <div class="notif-card {notif['css_class']}">
                <div class="notif-title">{notif['title']} - {notif['entity']}</div>
                <div class="notif-meta">📍 Παραλήπτης: <b>{notif['target_name']}</b> | 📞 {notif['target_phone'] or '---'} | ✉️ {notif['target_email'] or '---'}</div>
                <div class="notif-text">{notif['message']}</div>
                <div>
                    <a href="{sms_link}" class="link-btn btn-sms" target="_blank">📱 SMS</a>
                    <a href="{viber_link}" class="link-btn btn-viber" target="_blank">💜 Viber</a>
                    <a href="{email_link}" class="link-btn btn-email" target="_blank">📧 Email</a>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        if st.button(f"✅ Καταγραφή ως Σταλμένο", key=f"btn_{notif['type']}"):
            try:
                log_id = f"LOG-{uuid.uuid4().hex[:6].upper()}"
                gsheets_service.add_notification_log([log_id, today.strftime("%Y-%m-%d"), notif['target_name'], notif['type'], notif['message']])
                st.success("Η ειδοποίηση καταγράφηκε και απομακρύνθηκε!")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Σφάλμα καταγραφής: {e}")
