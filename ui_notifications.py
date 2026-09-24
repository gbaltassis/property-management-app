import streamlit as st
import gsheets_service
import pandas as pd
from datetime import date, datetime
import requests
import time
import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

COMMON_CSS = """
<style>
    html, body { font-family: sans-serif; background-color: transparent; }
    
    /* Ελαφρύ γκρι/λευκό φόντο για τα πλαίσια (containers) του Streamlit */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #fcfcfc;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
        padding: 5px;
    }
    
    @media (prefers-color-scheme: dark) {
        [data-testid="stVerticalBlockBorderWrapper"] {
            background-color: #1e2127;
            border-color: #3b82f6;
        }
    }
</style>
"""

MACRODROID_URL = st.secrets.get("macrodroid_url", "")
EMAIL_SENDER = st.secrets.get("email_address", "")
EMAIL_PASSWORD = st.secrets.get("email_password", "")

def send_via_macrodroid(phone, message, channel):
    if not MACRODROID_URL:
        st.error("Σφάλμα: Δεν έχει οριστεί το 'macrodroid_url' στα Secrets!")
        return False
    try:
        params = {"number": phone, "message": message, "channel": channel}
        response = requests.get(MACRODROID_URL, params=params, timeout=15)
        if response.status_code == 200:
            return True
        else:
            st.error(f"Το MacroDroid επέστρεψε σφάλμα: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        st.error(f"Αποτυχία επικοινωνίας με το MacroDroid: {e}")
        return False

def send_via_email(to_email, subject, message):
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        st.error("Δεν έχουν ρυθμιστεί τα στοιχεία Email στα Secrets.")
        return False
    if not to_email or to_email == 'nan':
        st.error("Δεν υπάρχει καταχωρημένο Email για αυτή την επαφή.")
        return False
        
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(message, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Αποτυχία αποστολής Email: {e}")
        return False

def check_already_sent(log_df, n_type, today_str):
    if log_df.empty or 'Type' not in log_df.columns or 'Date_Sent' not in log_df.columns:
        return False
    match = log_df[(log_df['Type'] == n_type) & (log_df['Date_Sent'] == today_str)]
    return not match.empty

# -------------------------------------------------------------
# ΑΝΑΔΥΟΜΕΝΟ ΠΑΡΑΘΥΡΟ ΓΙΑ ΜΕΜΟΝΩΜΕΝΗ ΕΙΔΟΠΟΙΗΣΗ
# -------------------------------------------------------------
@st.dialog("✍️ Δημιουργία Μεμονωμένης Ειδοποίησης")
def manual_notification_dialog(tenants_df, owners_df, today_str):
    all_contacts = {}
    if not tenants_df.empty:
        for _, t in tenants_df.iterrows():
            if str(t.get("Όνομα")) != "ΔΙΑΓΡΑΜΜΕΝΟ":
                all_contacts[f"Ενοικιαστής: {t.get('Επώνυμο', '')} {t.get('Όνομα', '')} ({t.get('Tenant_ID', '')})"] = {"phone": t.get("Κινητό"), "email": t.get("Email")}
    if not owners_df.empty:
        for _, o in owners_df.iterrows():
            if str(o.get("Όνομα")) != "ΔΙΑΓΡΑΜΜΕΝΟ":
                all_contacts[f"Ιδιοκτήτης: {o.get('Επώνυμο', '')} {o.get('Όνομα', '')} ({o.get('Owner_ID', '')})"] = {"phone": o.get("Κινητό"), "email": o.get("Email")}

    selected_contact = st.selectbox("Επιλογή Παραλήπτη από Μητρώο:", ["-- Επιλέξτε Επαφή --"] + list(all_contacts.keys()))
    
    custom_phone = ""
    custom_email = ""
    if selected_contact != "-- Επιλέξτε Επαφή --":
        custom_phone = str(all_contacts[selected_contact]["phone"]).replace('nan', '').replace(' ', '')
        custom_email = str(all_contacts[selected_contact]["email"]).replace('nan', '').replace(' ', '')
        
    c_ph, c_em = st.columns(2)
    man_phone = c_ph.text_input("Κινητό Παραλήπτη", value=custom_phone)
    man_email = c_em.text_input("Email Παραλήπτη", value=custom_email)
    
    man_msg = st.text_area("Κείμενο Ειδοποίησης", height=120, key="man_msg")
    
    st.write("Επιλέξτε μέσο αποστολής:")
    mc1, mc2, mc3 = st.columns(3)
    
    if mc1.button("📱 SMS", key="man_sms", type="primary", use_container_width=True):
        if not man_phone: st.warning("Συμπληρώστε κινητό.")
        elif send_via_macrodroid(man_phone, man_msg, "sms"):
            log_target = selected_contact.split(' (')[0] if selected_contact != "-- Επιλέξτε Επαφή --" else "Χειροκίνητη επαφή"
            gsheets_service.add_notification_log([f"LOG-{uuid.uuid4().hex[:6].upper()}", today_str, log_target, "MANUAL", f"[SMS] {man_msg}"])
            st.success("Εστάλη επιτυχώς!")
            time.sleep(1.5)
            st.rerun()
            
    if mc2.button("🟩 WhatsApp", key="man_wa", type="primary", use_container_width=True):
        if not man_phone: st.warning("Συμπληρώστε κινητό.")
        elif send_via_macrodroid(man_phone, man_msg, "whatsapp"):
            log_target = selected_contact.split(' (')[0] if selected_contact != "-- Επιλέξτε Επαφή --" else "Χειροκίνητη επαφή"
            gsheets_service.add_notification_log([f"LOG-{uuid.uuid4().hex[:6].upper()}", today_str, log_target, "MANUAL", f"[WhatsApp] {man_msg}"])
            st.success("Εστάλη επιτυχώς!")
            time.sleep(1.5)
            st.rerun()
            
    if mc3.button("📧 Email", key="man_em", type="primary", use_container_width=True):
        if not man_email: st.warning("Συμπληρώστε Email.")
        elif send_via_email(man_email, "Ενημέρωση από Διαχείριση", man_msg):
            log_target = selected_contact.split(' (')[0] if selected_contact != "-- Επιλέξτε Επαφή --" else "Χειροκίνητη επαφή"
            gsheets_service.add_notification_log([f"LOG-{uuid.uuid4().hex[:6].upper()}", today_str, log_target, "MANUAL", f"[Email] {man_msg}"])
            st.success("Εστάλη επιτυχώς!")
            time.sleep(1.5)
            st.rerun()

# -------------------------------------------------------------
# ΚΕΝΤΡΙΚΗ ΣΕΛΙΔΑ ΕΙΔΟΠΟΙΗΣΕΩΝ
# -------------------------------------------------------------
def show():
    st.markdown(COMMON_CSS, unsafe_allow_html=True)
    
    try:
        leases_df = gsheets_service.fetch_all_leases()
        insurances_df = gsheets_service.fetch_all_insurances()
        properties_df = gsheets_service.fetch_all_properties()
        tenants_df = gsheets_service.fetch_all_tenants()
        try: payments_df = gsheets_service.fetch_all_payments()
        except: payments_df = pd.DataFrame()
        try: owners_df = gsheets_service.fetch_all_owners()
        except: owners_df = pd.DataFrame()
        try: log_df = gsheets_service.fetch_all_notifications_log()
        except: log_df = pd.DataFrame(columns=["Log_ID", "Date_Sent", "Target", "Type", "Message"])
    except Exception as e:
        st.error(f"Σφάλμα κατά τη φόρτωση δεδομένων: {e}")
        return

    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    
    col_title, col_btn = st.columns([3, 1])
    with col_title:
        st.header("🔔 Κέντρο Ειδοποιήσεων")
        st.caption("Το σύστημα ανιχνεύει αυτόματα εκκρεμότητες και λήξεις.")
    with col_btn:
        st.write("") 
        if st.button("➕ Νέα Ειδοποίηση", use_container_width=True, type="secondary"):
            manual_notification_dialog(tenants_df, owners_df, today_str)
            
    st.markdown("---")

    pending_notifications = []
    auto_triggered_count = 0

    # 1. ΕΛΕΓΧΟΣ ΜΙΣΘΩΣΕΩΝ
    if not leases_df.empty:
        for _, lease in leases_df.iterrows():
            l_id = str(lease.get("Lease_ID", ""))
            try: end_d = datetime.strptime(str(lease.get("End_Date", "")), "%Y-%m-%d").date()
            except: continue
            
            days_left = (end_d - today).days
            p_id = str(lease.get("Property_ID", ""))
            p_match = properties_df[properties_df["Property_ID"] == p_id] if not properties_df.empty else pd.DataFrame()
            p_char = str(p_match.iloc[0].get("Χαρακτηριστικό", "Το ακίνητο")) if not p_match.empty else "Το ακίνητο"
            
            p_area = str(p_match.iloc[0].get("Περιοχή/Δήμος", "-")) if not p_match.empty else "-"
            p_street = str(p_match.iloc[0].get("Διεύθυνση", "-")) if not p_match.empty else "-"
            p_num = str(p_match.iloc[0].get("Αριθμός", "")) if not p_match.empty else ""

            # Εύρεση όλων των ενοικιαστών
            t_ids = [t.strip() for t in str(lease.get("Tenant_ID", "")).split(',') if t.strip()]
            t_full_names, t_phones = [], []
            for t_id in t_ids:
                t_match = tenants_df[tenants_df["Tenant_ID"] == t_id]
                if not t_match.empty:
                    t_full_names.append(f"{t_match.iloc[0].get('Όνομα', '')} {t_match.iloc[0].get('Επώνυμο', '')}".strip())
                    t_phones.append(str(t_match.iloc[0].get('Κινητό', '')).replace(" ", ""))
            
            t_names_str = ", ".join(t_full_names) if t_full_names else "Άγνωστος Ενοικιαστής"
            t_phones_str = ", ".join(t_phones) if t_phones else "-"

            # Συγκέντρωση ΜΟΝΑΔΙΚΩΝ Ιδιοκτητών (Αποφυγή διπλοεγγραφών λόγω ψιλής/επικαρπίας)
            unique_afms = set()
            o_full_names = []
            if not p_match.empty and not owners_df.empty:
                prop = p_match.iloc[0]
                for i in range(1, 4):
                    afm_raw = str(prop.get(f'AFM_{i}', '')).strip()
                    if len(afm_raw) == 8: afm_raw = "0" + afm_raw
                    if afm_raw and afm_raw != 'nan' and afm_raw not in unique_afms:
                        unique_afms.add(afm_raw)
                        o_match_global = owners_df[owners_df['ΑΦΜ'].astype(str).str.zfill(9) == afm_raw.zfill(9)]
                        if not o_match_global.empty:
                            o_raw = f"{o_match_global.iloc[0].get('Όνομα', '')} {o_match_global.iloc[0].get('Επώνυμο', '')}".strip()
                            o_full_names.append(o_raw)
            o_names_str = ", ".join(o_full_names) if o_full_names else "Άγνωστος Ιδιοκτήτης"

            # --- ΑΥΤΟΜΑΤΕΣ ΕΙΔΟΠΟΙΗΣΕΙΣ ΙΔΙΟΚΤΗΤΩΝ ΓΙΑ ΛΗΞΗ ΜΙΣΘΩΣΗΣ ---
            if days_left in [20, 10, 2] and unique_afms and not owners_df.empty:
                for afm in unique_afms:
                    o_match = owners_df[owners_df['ΑΦΜ'].astype(str).str.zfill(9) == afm.zfill(9)]
                    if not o_match.empty:
                        o_raw_name = f"{o_match.iloc[0].get('Όνομα', '')} {o_match.iloc[0].get('Επώνυμο', '')}".strip()
                        o_email = str(o_match.iloc[0].get("Email", ""))
                        o_phone = str(o_match.iloc[0].get("Κινητό", "")).replace(" ", "")

                        o_title = str(o_match.iloc[0].get("Τίτλος", "")).strip()
                        if not o_title or o_title == 'nan': o_title = "Αγαπητέ Κύριε/Κυρία"
                        
                        o_prosfonisi = str(o_match.iloc[0].get("Προσφώνηση", "")).strip()
                        o_vocative = o_prosfonisi if o_prosfonisi and o_prosfonisi != 'nan' else o_raw_name
                        
                        o_greeting = f"{o_title} {o_vocative}".strip()

                        email_type = f"AUTO_OWNER_LEASE_EMAIL_{days_left}_{l_id}_{afm}"
                        if not check_already_sent(log_df, email_type, today_str):
                            subject = f"ΕΙΔΟΠΟΙΗΣΗ ΛΗΞΗΣ ΜΙΣΘΩΣΗΣ {p_char}"
                            body = f"{o_greeting},\n\nΗ μίσθωση για το ακίνητο ιδιοκτησίας σας {p_char} στην περιοχή {p_area} και επί της οδού {p_street} {p_num}, λήγει στις {end_d.strftime('%d/%m/%Y')}.\n\nΕνοικιαστής/ές: {t_names_str}."
                            if send_via_email(o_email, subject, body):
                                gsheets_service.add_notification_log([f"LOG-{uuid.uuid4().hex[:6].upper()}", today_str, o_raw_name, email_type, f"[Auto Email] Λήξη Μίσθωσης"])
                                st.toast(f"✅ Εστάλη αυτόματο Email στον/στην {o_raw_name} για λήξη μίσθωσης.")
                                auto_triggered_count += 1
                                
                        if days_left == 2:
                            sms_type = f"AUTO_OWNER_LEASE_SMS_2_{l_id}_{afm}"
                            if not check_already_sent(log_df, sms_type, today_str):
                                sms_body = f"Η μίσθωση για το ακίνητο ιδιοκτησίας σας {p_char} στην περιοχή {p_area} και επί της οδού {p_street} {p_num}, λήγει στις {end_d.strftime('%d/%m/%Y')}. Ενοικιαστής {t_names_str}, {t_phones_str}."
                                if send_via_macrodroid(o_phone, sms_body, "sms"):
                                    gsheets_service.add_notification_log([f"LOG-{uuid.uuid4().hex[:6].upper()}", today_str, o_raw_name, sms_type, f"[Auto SMS] Λήξη Μίσθωσης"])
                                    st.toast(f"✅ Εστάλη αυτόματο SMS στον/στην {o_raw_name} για λήξη μίσθωσης.")
                                    auto_triggered_count += 1

            # --- ΧΕΙΡΟΚΙΝΗΤΕΣ ΕΙΔΟΠΟΙΗΣΕΙΣ ΕΝΟΙΚΙΑΣΤΩΝ ΣΤΗΝ ΟΘΟΝΗ (30 & 10 Μέρες) ---
            if days_left in [30, 10]:
                for t_id in t_ids:
                    t_match = tenants_df[tenants_df["Tenant_ID"] == t_id]
                    if not t_match.empty:
                        t_name = str(t_match.iloc[0].get("Όνομα", ""))
                        t_phone = str(t_match.iloc[0].get("Κινητό", "")).replace(" ", "")
                        t_email = str(t_match.iloc[0].get("Email", ""))
                        
                        t_title = str(t_match.iloc[0].get("Τίτλος", "")).strip()
                        if not t_title or t_title == 'nan': t_title = "Γεια σας"
                        
                        t_prosfonisi = str(t_match.iloc[0].get("Προσφώνηση", "")).strip()
                        t_vocative = t_prosfonisi if t_prosfonisi and t_prosfonisi != 'nan' else t_name
                        
                        t_greeting = f"{t_title} {t_vocative}".strip()
                        
                        notif_type = f"LEASE_{days_left}_{l_id}_{t_id}"
                        if not check_already_sent(log_df, notif_type, today_str):
                            msg = f"{t_greeting},\n\nΣας υπενθυμίζουμε ότι το μισθωτήριο για το ακίνητο στην περιοχή {p_area} και επί της οδού {p_street} {p_num}, λήγει σε {days_left} ημέρες ({end_d.strftime('%d/%m/%Y')}).\n\nΙδιοκτήτης/ες: {o_names_str}"
                            pending_notifications.append({
                                "Type": notif_type, "Property_Name": p_char, "Kind": "Λήξη Μισθωτηρίου",
                                "Date": end_d.strftime('%d/%m/%Y'), "Target_Phone": t_phone, "Target_Email": t_email, 
                                "Target_Name": f"{t_name}", "Title": f"🔔 Λήξη Μίσθωσης σε {days_left} μέρες", 
                                "Default_Message": msg,
                                "Email_Subject": f"ΕΙΔΟΠΟΙΗΣΗ ΛΗΞΗΣ ΜΙΣΘΩΣΗΣ {p_char}"
                            })

    # 2. ΕΛΕΓΧΟΣ ΑΣΦΑΛΙΣΤΗΡΙΩΝ
    if not insurances_df.empty:
        for _, ins in insurances_df.iterrows():
            i_id = str(ins.get("Insurance_ID", ""))
            i_num = str(ins.get("Contract_Number", "")).strip() # Αριθμός Συμβολαίου
            
            try: ren_d = datetime.strptime(str(ins.get("Renewal_Date", "")), "%Y-%m-%d").date()
            except: continue
            
            days_left = (ren_d - today).days
            if days_left in [15, 7, 2]:
                p_id = str(ins.get("Property_ID", ""))
                p_match = properties_df[properties_df["Property_ID"] == p_id] if not properties_df.empty else pd.DataFrame()
                p_char = str(p_match.iloc[0].get("Χαρακτηριστικό", "Το ακίνητο")) if not p_match.empty else "Το ακίνητο"
                
                if not p_match.empty and not owners_df.empty:
                    prop = p_match.iloc[0]
                    # Συγκέντρωση ΜΟΝΑΔΙΚΩΝ Ιδιοκτητών για τα ασφαλιστήρια
                    unique_afms = set()
                    for i in range(1, 4):
                        afm = str(prop.get(f'AFM_{i}', '')).strip()
                        if len(afm) == 8: afm = "0" + afm
                        if afm and afm != 'nan':
                            unique_afms.add(afm)
                            
                    for afm in unique_afms:
                        owner_match = owners_df[owners_df['ΑΦΜ'].astype(str).str.zfill(9) == afm.zfill(9)]
                        if not owner_match.empty:
                            o_name = str(owner_match.iloc[0].get("Όνομα", ""))
                            o_phone = str(owner_match.iloc[0].get("Κινητό", "")).replace(" ", "")
                            o_email = str(owner_match.iloc[0].get("Email", ""))
                            
                            o_title = str(owner_match.iloc[0].get("Τίτλος", "")).strip()
                            if not o_title or o_title == 'nan': o_title = "Αγαπητέ Κύριε/Κυρία"
                            
                            o_prosfonisi = str(owner_match.iloc[0].get("Προσφώνηση", "")).strip()
                            o_vocative = o_prosfonisi if o_prosfonisi and o_prosfonisi != 'nan' else o_name
                            
                            o_greeting = f"{o_title} {o_vocative}".strip()
                            
                            notif_type = f"INS_{days_left}_{i_id}_{afm}"
                            if not check_already_sent(log_df, notif_type, today_str):
                                msg = f"{o_greeting},\n\nΤο ασφαλιστήριο ({ins.get('Category')}) με αριθμό συμβολαίου {i_num} για το '{p_char}' λήγει σε {days_left} ημέρες ({ren_d.strftime('%d/%m/%Y')})."
                                pending_notifications.append({
                                    "Type": notif_type, "Property_Name": p_char, "Kind": f"Ασφάλεια ({ins.get('Category', '')})",
                                    "Date": ren_d.strftime('%d/%m/%Y'), "Target_Phone": o_phone, "Target_Email": o_email, 
                                    "Target_Name": f"{o_name}", "Title": f"🛡️ Λήξη Ασφαλιστηρίου σε {days_left} μέρες", 
                                    "Default_Message": msg,
                                    "Email_Subject": f"ΕΙΔΟΠΟΙΗΣΗ ΛΗΞΗΣ ΑΣΦΑΛΙΣΤΗΡΙΟΥ {p_char}"
                                })

    # 3. ΕΛΕΓΧΟΣ ΕΚΚΡΕΜΩΝ ΟΦΕΙΛΩΝ / ΕΙΣΠΡΑΞΕΩΝ
    if not payments_df.empty and 'Status' in payments_df.columns:
        pending_payments = payments_df[payments_df['Status'] == 'Εκκρεμεί']
        
        for _, pay in pending_payments.iterrows():
            pay_id = str(pay.get("Payment_ID", ""))
            l_id = str(pay.get("Lease_ID", "")) 
            
            if not pay_id or pay_id == 'nan' or not l_id or l_id == 'nan': 
                continue
            
            amount = str(pay.get("Amount", "0")).replace(".", ",")
            if amount == "0" or amount == "nan": 
                continue
                
            pay_type = str(pay.get("Payment_Type", "Οφειλή"))
            pay_desc = str(pay.get("Description", pay.get("Περιγραφή", "-")))
            pay_date_raw = str(pay.get("Date_Received", ""))
            
            try:
                due_date = datetime.strptime(pay_date_raw, "%Y-%m-%d").date()
                pay_date_str = due_date.strftime('%d/%m/%Y')
                days_late = (today - due_date).days
            except:
                continue 
                
            l_match = leases_df[leases_df['Lease_ID'] == l_id] if not leases_df.empty else pd.DataFrame()
            if l_match.empty: continue
                
            p_id = str(l_match.iloc[0].get("Property_ID", ""))
            p_match = properties_df[properties_df["Property_ID"] == p_id] if not properties_df.empty else pd.DataFrame()
            p_char = str(p_match.iloc[0].get("Χαρακτηριστικό", "Το ακίνητο")) if not p_match.empty else "Το ακίνητο"
            
            p_area = str(p_match.iloc[0].get("Περιοχή/Δήμος", "-")) if not p_match.empty else "-"
            p_street = str(p_match.iloc[0].get("Διεύθυνση", "-")) if not p_match.empty else "-"
            p_num = str(p_match.iloc[0].get("Αριθμός", "")) if not p_match.empty else ""
            
            t_ids = [t.strip() for t in str(l_match.iloc[0].get("Tenant_ID", "")).split(',') if t.strip()]
            t_full_names, t_phones = [], []
            for t_id in t_ids:
                t_m = tenants_df[tenants_df["Tenant_ID"] == t_id]
                if not t_m.empty:
                    t_full_names.append(f"{t_m.iloc[0].get('Όνομα', '')} {t_m.iloc[0].get('Επώνυμο', '')}".strip())
                    t_phones.append(str(t_m.iloc[0].get('Κινητό', '')).replace(" ", ""))
            t_names_str = ", ".join(t_full_names) if t_full_names else "Άγνωστος Ενοικιαστής"

            # Συγκέντρωση ΜΟΝΑΔΙΚΩΝ Ιδιοκτητών για τις Οφειλές
            unique_afms = set()
            if not p_match.empty and not owners_df.empty:
                prop = p_match.iloc[0]
                for i in range(1, 4):
                    afm_raw = str(prop.get(f'AFM_{i}', '')).strip()
                    if len(afm_raw) == 8: afm_raw = "0" + afm_raw
                    if afm_raw and afm_raw != 'nan':
                        unique_afms.add(afm_raw)

            # --- ΑΥΤΟΜΑΤΕΣ ΕΙΔΟΠΟΙΗΣΕΙΣ ΙΔΙΟΚΤΗΤΩΝ ΓΙΑ ΚΑΘΥΣΤΕΡΗΣΗ ΟΦΕΙΛΗΣ ---
            if days_late in [10, 15] and unique_afms and not owners_df.empty:
                for afm in unique_afms:
                    o_match = owners_df[owners_df['ΑΦΜ'].astype(str).str.zfill(9) == afm.zfill(9)]
                    if not o_match.empty:
                        o_raw_name = f"{o_match.iloc[0].get('Όνομα', '')} {o_match.iloc[0].get('Επώνυμο', '')}".strip()
                        o_email = str(o_match.iloc[0].get("Email", ""))
                        
                        o_title = str(o_match.iloc[0].get("Τίτλος", "")).strip()
                        if not o_title or o_title == 'nan': o_title = "Αγαπητέ Κύριε/Κυρία"
                        
                        o_prosfonisi = str(o_match.iloc[0].get("Προσφώνηση", "")).strip()
                        o_vocative = o_prosfonisi if o_prosfonisi and o_prosfonisi != 'nan' else o_raw_name
                        
                        o_greeting = f"{o_title} {o_vocative}".strip()
                        
                        email_type = f"AUTO_OWNER_PAY_EMAIL_{days_late}_{pay_id}_{afm}"
                        if not check_already_sent(log_df, email_type, today_str):
                            subject = f"ΕΙΔΟΠΟΙΗΣΗ ΕΚΚΡΕΜΟΥΣ ΟΦΕΙΛΗΣ {p_area} {p_street} {p_num}".strip()
                            body = f"{o_greeting},\n\nΣας στέλνουμε για το ακίνητο ιδιοκτησίας σας {p_char} στην περιοχή {p_area} και επί της οδού {p_street} {p_num}.\nΣας υπενθυμίζουμε πως εκκρεμεί η οφειλή για το {pay_type.lower()}, {pay_desc}, από τις {pay_date_str}.\n\nΠαρακαλούμε επικοινωνήστε με τον ενοικιαστή σας {t_names_str} για την τακτοποίηση της οφειλής."
                            if send_via_email(o_email, subject, body):
                                gsheets_service.add_notification_log([f"LOG-{uuid.uuid4().hex[:6].upper()}", today_str, o_raw_name, email_type, f"[Auto Email] Οφειλή"])
                                st.toast(f"✅ Εστάλη αυτόματο Email στον/στην {o_raw_name} για εκκρεμή οφειλή.")
                                auto_triggered_count += 1

            # --- ΧΕΙΡΟΚΙΝΗΤΕΣ ΕΙΔΟΠΟΙΗΣΕΙΣ ΕΝΟΙΚΙΑΣΤΩΝ ΣΤΗΝ ΟΘΟΝΗ ---
            for t_id in t_ids:
                t_match = tenants_df[tenants_df["Tenant_ID"] == t_id] if 'Tenant_ID' in tenants_df.columns else pd.DataFrame()
                if not t_match.empty:
                    t_name = str(t_match.iloc[0].get("Όνομα", ""))
                    t_phone = str(t_match.iloc[0].get("Κινητό", "")).replace(" ", "")
                    t_email = str(t_match.iloc[0].get("Email", ""))
                    
                    t_title = str(t_match.iloc[0].get("Τίτλος", "")).strip()
                    if not t_title or t_title == 'nan': t_title = "Γεια σας"
                    
                    t_prosfonisi = str(t_match.iloc[0].get("Προσφώνηση", "")).strip()
                    t_vocative = t_prosfonisi if t_prosfonisi and t_prosfonisi != 'nan' else t_name
                    
                    t_greeting = f"{t_title} {t_vocative}".strip()
                    
                    notif_type = f"PAY_{pay_id}_{t_id}"
                    if not check_already_sent(log_df, notif_type, today_str):
                        msg = f"{t_greeting},\n\nΕκκρεμεί από {pay_date_str} η εξόφληση για το {pay_type.lower()}, ποσού {amount}€ για το ακίνητο στην περιοχή {p_area}, επί της οδού {p_street} {p_num}."
                        pending_notifications.append({
                            "Type": notif_type, "Property_Name": p_char, "Kind": f"{pay_type} ({amount}€)",
                            "Date": pay_date_str, "Target_Phone": t_phone, "Target_Email": t_email, 
                            "Target_Name": f"{t_name}", "Title": f"⚠️ Εκκρεμής Οφειλή: {amount}€", 
                            "Default_Message": msg,
                            "Email_Subject": f"ΕΙΔΟΠΟΙΗΣΗ ΕΚΚΡΕΜΟΥΣ ΟΦΕΙΛΗΣ {p_area} {p_street} {p_num}".strip()
                        })

    if auto_triggered_count > 0:
        time.sleep(2)
        st.rerun()

    if not pending_notifications:
        st.success("🎉 Δεν υπάρχουν εκκρεμείς ειδοποιήσεις για σήμερα.")
    else:
        st.warning(f"Έχετε {len(pending_notifications)} ειδοποιήσεις προς επεξεργασία και αποστολή.")
        
        for idx, notif in enumerate(pending_notifications):
            with st.container(border=True):
                st.markdown(f"#### {notif['Title']}")
                
                c1, c2, c3, c4 = st.columns(4)
                c1.markdown(f"**🏠 Ακίνητο / Μίσθωση**<br><span style='font-size: 14px; color: #444;'>{notif['Property_Name']}</span>", unsafe_allow_html=True)
                c2.markdown(f"**📄 Είδος Ειδοποίησης**<br><span style='font-size: 14px; color: #444;'>{notif['Kind']}</span>", unsafe_allow_html=True)
                c3.markdown(f"**📅 Ημερομηνία**<br><span style='font-size: 14px; color: #444;'>{notif['Date']}</span>", unsafe_allow_html=True)
                
                target_phone = notif.get('Target_Phone', '-')
                target_email = notif.get('Target_Email', '-')
                c4.markdown(f"**👤 Παραλήπτης**<br><span style='font-size: 14px; color: #444;'>**{notif['Target_Name']}**<br>📞 {target_phone}<br>📧 {target_email}</span>", unsafe_allow_html=True)
                
                st.write("") 
                final_message = st.text_area("📝 Προτεινόμενο κείμενο μηνύματος (Επεξεργάσιμο):", value=notif['Default_Message'], height=100, key=f"msg_{idx}")
                
                b1, b2, b3 = st.columns(3)
                
                if b1.button("📱 SMS", key=f"btn_sms_{idx}", type="primary", use_container_width=True):
                    with st.spinner("Αποστολή SMS..."):
                        if send_via_macrodroid(notif["Target_Phone"], final_message, "sms"):
                            log_id = f"LOG-{uuid.uuid4().hex[:6].upper()}"
                            gsheets_service.add_notification_log([log_id, today_str, notif["Target_Name"], notif["Type"], f"[SMS] {final_message}"])
                            st.success("Το SMS στάλθηκε!")
                            time.sleep(1)
                            st.rerun()
                            
                if b2.button("🟩 WhatsApp", key=f"btn_wa_{idx}", type="primary", use_container_width=True):
                    with st.spinner("Εντολή WhatsApp..."):
                        if send_via_macrodroid(notif["Target_Phone"], final_message, "whatsapp"):
                            log_id = f"LOG-{uuid.uuid4().hex[:6].upper()}"
                            gsheets_service.add_notification_log([log_id, today_str, notif["Target_Name"], notif["Type"], f"[WhatsApp] {final_message}"])
                            st.success("Η εντολή WhatsApp στάλθηκε!")
                            time.sleep(1)
                            st.rerun()
                            
                if b3.button("📧 Email", key=f"btn_em_{idx}", type="primary", use_container_width=True):
                    with st.spinner("Αποστολή Email..."):
                        email_subj = notif.get("Email_Subject", "Ενημέρωση από Διαχείριση")
                        if send_via_email(notif["Target_Email"], email_subj, final_message):
                            log_id = f"LOG-{uuid.uuid4().hex[:6].upper()}"
                            gsheets_service.add_notification_log([log_id, today_str, notif["Target_Name"], notif["Type"], f"[Email] {final_message}"])
                            st.success("Το Email στάλθηκε!")
                            time.sleep(1)
                            st.rerun()
