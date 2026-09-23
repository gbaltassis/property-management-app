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
    .notif-card { background-color: #f8f9fa; border-left: 4px solid #007bff; border-radius: 8px; padding: 15px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .notif-urgent { border-left-color: #dc3545; background-color: #fff3cd; }
    .notif-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; }
    .notif-title { font-weight: bold; color: #31333F; font-size: 15px; }
    .notif-target { font-size: 12px; color: #6c757d; background: #e9ecef; padding: 4px 8px; border-radius: 4px; }
    .channel-btn { width: 100%; border: none; padding: 8px; border-radius: 4px; color: white; font-weight: bold; cursor: pointer; transition: opacity 0.2s; }
    .channel-btn:hover { opacity: 0.8; }
    
    @media (prefers-color-scheme: dark) {
        .notif-card { background-color: #1e2127; border-left-color: #3b82f6; box-shadow: 0 1px 3px rgba(0,0,0,0.3); }
        .notif-urgent { border-left-color: #ef4444; background-color: #2e1c1c; }
        .notif-title { color: #f8f9fa; }
        .notif-target { background: #2d3748; color: #a0aec0; }
    }
</style>
"""

# Ανάγνωση Secrets
MACRODROID_URL = st.secrets.get("macrodroid_url", "")
EMAIL_SENDER = st.secrets.get("email_address", "")
EMAIL_PASSWORD = st.secrets.get("email_password", "")

def send_via_macrodroid(phone, message, channel):
    if not MACRODROID_URL:
        st.error("Σφάλμα: Δεν έχει οριστεί το 'macrodroid_url' στα Secrets!")
        return False
    try:
        # Στέλνουμε το τηλέφωνο, το κείμενο ΚΑΙ το κανάλι επικοινωνίας
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
        
        # Χρήση του Gmail SMTP (Αν χρησιμοποιείς άλλο πάροχο, πρέπει να αλλάξει ο server)
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Αποτυχία αποστολής Email: {e}")
        return False

def show():
    st.markdown(COMMON_CSS, unsafe_allow_html=True)
    st.header("🔔 Κέντρο Ειδοποιήσεων")
    st.caption("Επεξεργαστείτε το κείμενο αν επιθυμείτε και πατήστε το κανάλι αποστολής.")

    try:
        leases_df = gsheets_service.fetch_all_leases()
        insurances_df = gsheets_service.fetch_all_insurances()
        properties_df = gsheets_service.fetch_all_properties()
        tenants_df = gsheets_service.fetch_all_tenants()
        try: owners_df = gsheets_service.fetch_all_owners()
        except: owners_df = pd.DataFrame()
        try: log_df = gsheets_service.fetch_all_notifications_log()
        except: log_df = pd.DataFrame(columns=["Log_ID", "Date_Sent", "Target", "Type", "Message"])
    except Exception as e:
        st.error(f"Σφάλμα κατά τη φόρτωση δεδομένων: {e}")
        return

    today = date.today()
    pending_notifications = []

    # 1. ΕΛΕΓΧΟΣ ΜΙΣΘΩΣΕΩΝ (30 & 10 μέρες πριν)
    if not leases_df.empty:
        for _, lease in leases_df.iterrows():
            l_id = str(lease.get("Lease_ID", ""))
            try: end_d = datetime.strptime(str(lease.get("End_Date", "")), "%Y-%m-%d").date()
            except: continue
            
            days_left = (end_d - today).days
            if days_left in [30, 10]:
                p_id = str(lease.get("Property_ID", ""))
                p_match = properties_df[properties_df["Property_ID"] == p_id] if not properties_df.empty else pd.DataFrame()
                p_name = str(p_match.iloc[0].get("Χαρακτηριστικό", "Το ακίνητο")) if not p_match.empty else "Το ακίνητο"
                
                t_ids = [t.strip() for t in str(lease.get("Tenant_ID", "")).split(',') if t.strip()]
                for t_id in t_ids:
                    t_match = tenants_df[tenants_df["Tenant_ID"] == t_id]
                    if not t_match.empty:
                        t_name = str(t_match.iloc[0].get("Όνομα", ""))
                        t_phone = str(t_match.iloc[0].get("Κινητό", "")).replace(" ", "")
                        t_email = str(t_match.iloc[0].get("Email", ""))
                        
                        notif_type = f"LEASE_{days_left}_{l_id}_{t_id}"
                        already_sent = False
                        if not log_df.empty and 'Type' in log_df.columns:
                            already_sent = not log_df[log_df['Type'] == notif_type].empty
                        
                        if not already_sent:
                            msg = f"Γεια σας {t_name}. Σας υπενθυμίζουμε ότι το μισθωτήριο για το ακίνητο '{p_name}' λήγει σε {days_left} ημέρες ({end_d.strftime('%d/%m/%Y')}). Παρακαλούμε επικοινωνήστε μαζί μας."
                            pending_notifications.append({
                                "Type": notif_type, "Target_Phone": t_phone, "Target_Email": t_email, "Target_Name": f"Ενοικιαστής: {t_name}", 
                                "Title": f"Λήξη Μίσθωσης σε {days_left} μέρες ({p_name})", "Default_Message": msg, "Urgent": days_left <= 10
                            })

    # 2. ΕΛΕΓΧΟΣ ΑΣΦΑΛΙΣΤΗΡΙΩΝ (15, 7 & 2 μέρες πριν)
    if not insurances_df.empty:
        for _, ins in insurances_df.iterrows():
            i_id = str(ins.get("Insurance_ID", ""))
            try: ren_d = datetime.strptime(str(ins.get("Renewal_Date", "")), "%Y-%m-%d").date()
            except: continue
            
            days_left = (ren_d - today).days
            if days_left in [15, 7, 2]:
                p_id = str(ins.get("Property_ID", ""))
                p_match = properties_df[properties_df["Property_ID"] == p_id] if not properties_df.empty else pd.DataFrame()
                p_name = str(p_match.iloc[0].get("Χαρακτηριστικό", "Το ακίνητο")) if not p_match.empty else "Το ακίνητο"
                
                if not p_match.empty and not owners_df.empty:
                    prop = p_match.iloc[0]
                    notified_afms = set()
                    
                    for i in range(1, 4):
                        afm = str(prop.get(f'AFM_{i}', '')).strip()
                        if len(afm) == 8: afm = "0" + afm
                        
                        if afm and afm != 'nan' and afm not in notified_afms:
                            owner_match = owners_df[owners_df['ΑΦΜ'].astype(str).str.zfill(9) == afm.zfill(9)]
                            if not owner_match.empty:
                                o_name = str(owner_match.iloc[0].get("Όνομα", ""))
                                o_phone = str(owner_match.iloc[0].get("Κινητό", "")).replace(" ", "")
                                o_email = str(owner_match.iloc[0].get("Email", ""))
                                
                                notif_type = f"INS_{days_left}_{i_id}_{afm}"
                                already_sent = False
                                if not log_df.empty and 'Type' in log_df.columns:
                                    already_sent = not log_df[log_df['Type'] == notif_type].empty
                                
                                if not already_sent:
                                    msg = f"Αξιότιμε/η {o_name}, σας ενημερώνουμε ότι το ασφαλιστήριο ({ins.get('Category')}) για το '{p_name}' λήγει σε {days_left} ημέρες ({ren_d.strftime('%d/%m/%Y')})."
                                    pending_notifications.append({
                                        "Type": notif_type, "Target_Phone": o_phone, "Target_Email": o_email, "Target_Name": f"Ιδιοκτήτης: {o_name}", 
                                        "Title": f"Λήξη Ασφαλιστηρίου σε {days_left} μέρες ({p_name})", "Default_Message": msg, "Urgent": days_left <= 7
                                    })
                                    notified_afms.add(afm)

    # -------------------------------------------------------------
    # ΟΠΤΙΚΟΠΟΙΗΣΗ & ΔΙΑΧΕΙΡΙΣΗ
    # -------------------------------------------------------------
    st.markdown("---")
    
    if not pending_notifications:
        st.success("🎉 Δεν υπάρχουν εκκρεμείς ειδοποιήσεις για σήμερα.")
    else:
        st.warning(f"Έχετε {len(pending_notifications)} ειδοποιήσεις προς επεξεργασία και αποστολή.")
        
        for idx, notif in enumerate(pending_notifications):
            urgency_class = "notif-urgent" if notif["Urgent"] else ""
            
            with st.container():
                st.markdown(f"""
                <div class="notif-card {urgency_class}">
                    <div class="notif-header">
                        <div class="notif-title">{notif['Title']}</div>
                        <div class="notif-target">👤 {notif['Target_Name']} <br> 📞 {notif.get('Target_Phone','-')} | 📧 {notif.get('Target_Email','-')}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Το πεδίο κειμένου είναι επεξεργάσιμο από εσένα!
                final_message = st.text_area("Επεξεργασία Κειμένου:", value=notif['Default_Message'], height=100, key=f"msg_{idx}")
                
                c1, c2, c3, c4 = st.columns(4)
                
                # ΑΠΟΣΤΟΛΗ SMS (Μέσω MacroDroid: app=sms)
                if c1.button("📱 SMS", key=f"btn_sms_{idx}", type="primary", use_container_width=True):
                    with st.spinner("Αποστολή SMS..."):
                        if send_via_macrodroid(notif["Target_Phone"], final_message, "sms"):
                            log_id = f"LOG-{uuid.uuid4().hex[:6].upper()}"
                            gsheets_service.add_notification_log([log_id, today.strftime("%Y-%m-%d"), notif["Target_Name"], notif["Type"], f"[SMS] {final_message}"])
                            st.success("Το SMS στάλθηκε!")
                            time.sleep(1)
                            st.rerun()
                            
                # ΑΠΟΣΤΟΛΗ VIBER (Μέσω MacroDroid: app=viber)
                if c2.button("💜 Viber", key=f"btn_vib_{idx}", type="primary", use_container_width=True):
                    with st.spinner("Εντολή Viber..."):
                        if send_via_macrodroid(notif["Target_Phone"], final_message, "viber"):
                            log_id = f"LOG-{uuid.uuid4().hex[:6].upper()}"
                            gsheets_service.add_notification_log([log_id, today.strftime("%Y-%m-%d"), notif["Target_Name"], notif["Type"], f"[Viber] {final_message}"])
                            st.success("Η εντολή Viber στάλθηκε!")
                            time.sleep(1)
                            st.rerun()

                # ΑΠΟΣΤΟΛΗ WHATSAPP (Μέσω MacroDroid: app=whatsapp)
                if c3.button("🟩 WhatsApp", key=f"btn_wa_{idx}", type="primary", use_container_width=True):
                    with st.spinner("Εντολή WhatsApp..."):
                        if send_via_macrodroid(notif["Target_Phone"], final_message, "whatsapp"):
                            log_id = f"LOG-{uuid.uuid4().hex[:6].upper()}"
                            gsheets_service.add_notification_log([log_id, today.strftime("%Y-%m-%d"), notif["Target_Name"], notif["Type"], f"[WhatsApp] {final_message}"])
                            st.success("Η εντολή WhatsApp στάλθηκε!")
                            time.sleep(1)
                            st.rerun()
                            
                # ΑΠΟΣΤΟΛΗ EMAIL (Απευθείας από την Python)
                if c4.button("📧 Email", key=f"btn_em_{idx}", type="primary", use_container_width=True):
                    with st.spinner("Αποστολή Email..."):
                        if send_via_email(notif["Target_Email"], notif["Title"], final_message):
                            log_id = f"LOG-{uuid.uuid4().hex[:6].upper()}"
                            gsheets_service.add_notification_log([log_id, today.strftime("%Y-%m-%d"), notif["Target_Name"], notif["Type"], f"[Email] {final_message}"])
                            st.success("Το Email στάλθηκε!")
                            time.sleep(1)
                            st.rerun()
                st.write("")
