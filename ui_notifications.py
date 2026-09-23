import streamlit as st
import pandas as pd
import gsheets_service
from datetime import datetime, date
import uuid
import urllib.parse
import time
import streamlit.components.v1 as components
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

COMMON_CSS = """
<style>
    .notif-card { background-color: #ffffff; border-left: 5px solid #007bff; border-radius: 6px; padding: 15px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .notif-warning { border-left-color: #ffc107; }
    .notif-danger { border-left-color: #dc3545; }
    .notif-debt { border-left-color: #fd7e14; }
    .notif-custom { border-left-color: #17a2b8; }
    .notif-title { font-size: 16px; font-weight: bold; color: #31333F; margin-bottom: 5px; }
    .notif-meta { font-size: 11px; color: #888; margin-bottom: 10px; }
    .link-btn { display: inline-block; padding: 6px 12px; margin-right: 5px; margin-bottom: 5px; border-radius: 4px; text-decoration: none; font-size: 12px; font-weight: bold; color: white !important; text-align: center; cursor: pointer; transition: opacity 0.2s; border: none; }
    .link-btn:hover { opacity: 0.8; }
    .btn-sms { background-color: #28a745; }
    .btn-viber { background-color: #665CAC; }
    .btn-wa { background-color: #25D366; }
    .btn-copy { background-color: #6c757d; }
</style>
"""

COPY_JS = """
<script>
    function copyTextToClipboard(textId) {
        var copyText = document.getElementById(textId).innerText || document.getElementById(textId).value;
        navigator.clipboard.writeText(copyText).then(function() {
            alert("Το κείμενο αντιγράφηκε! Μπορείτε να κάνετε Επικόλληση (Paste).");
        }, function(err) {
            console.error('Αποτυχία αντιγραφής: ', err);
        });
    }
</script>
"""

def send_direct_email(to_email, subject, body):
    try:
        sender_email = st.secrets.get("GMAIL_USER")
        sender_password = st.secrets.get("GMAIL_PASS")
        
        if not sender_email or not sender_password:
            return False, "Δεν έχουν ρυθμιστεί τα GMAIL_USER και GMAIL_PASS στα secrets του Streamlit."

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True, "Το email στάλθηκε επιτυχώς!"
    except Exception as e:
        return False, str(e)

def show():
    if "custom_notif_mode" not in st.session_state: st.session_state.custom_notif_mode = False

    st.markdown(COMMON_CSS, unsafe_allow_html=True)
    components.html(COPY_JS, height=0)
    
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
    # 1. ΛΕΙΤΟΥΡΓΙΑ CUSTOM ΜΗΝΥΜΑΤΟΣ
    # =====================================================================
    if st.session_state.custom_notif_mode:
        st.markdown("### ✍️ Σύνταξη Νέου Μηνύματος")
        if st.button("⬅️ Ακύρωση", key="cancel_custom"):
            st.session_state.custom_notif_mode = False; st.rerun()
            
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
                        target_opts[afm] = {"name": f"{n} {s}".strip(), "phone": "", "email": ""}
                        
        t_keys = list(target_opts.keys())
        sel_target_id = st.selectbox("Επιλέξτε Παραλήπτη", t_keys, format_func=lambda x: target_opts[x]['name']) if t_keys else None
        
        c_msg = st.text_area("Κείμενο Μηνύματος", placeholder="Γράψτε εδώ το μήνυμά σας...")
        
        if sel_target_id and c_msg:
            t_info = target_opts[sel_target_id]
            encoded_msg = urllib.parse.quote(c_msg)
            clean_phone = t_info['phone'].replace(' ', '')
            if clean_phone and not clean_phone.startswith('+30') and not clean_phone.startswith('0030'): clean_phone = f"+30{clean_phone}"
            
            st.markdown(f"**Στοιχεία:** 📞 {t_info['phone'] or '---'} | ✉️ {t_info['email'] or '---'}")
            
            c1, c2, c3, c4 = st.columns(4)
            sms_link = f"sms:{clean_phone}?body={encoded_msg}" if clean_phone else "#"
            viber_link = f"viber://chat?number={clean_phone}" if clean_phone else "#"
            wa_link = f"https://wa.me/{clean_phone.replace('+','')}?text={encoded_msg}" if clean_phone else "#"
            
            c1.markdown(f'<a href="{viber_link}" class="link-btn btn-viber" target="_blank" style="width:100%;">💜 Viber</a>', unsafe_allow_html=True)
            c2.markdown(f'<a href="{wa_link}" class="link-btn btn-wa" target="_blank" style="width:100%;">💬 WhatsApp</a>', unsafe_allow_html=True)
            c3.markdown(f'<a href="{sms_link}" class="link-btn btn-sms" target="_blank" style="width:100%;">📱 SMS App</a>', unsafe_allow_html=True)
            
            if c4.button("📧 Άμεση Αποστολή Email", type="primary", use_container_width=True):
                if t_info['email']:
                    success, msg_result = send_direct_email(t_info['email'], "Ενημέρωση από Property Management", c_msg)
                    if success: st.success(msg_result)
                    else: st.error(msg_result)
                else:
                    st.warning("Ο παραλήπτης δεν έχει δηλωμένο email.")
        return

    # =====================================================================
    # 2. ΣΥΛΛΟΓΗ ΑΥΤΟΜΑΤΩΝ ΕΙΔΟΠΟΙΗΣΕΩΝ (ΟΦΕΙΛΕΣ, ΑΣΦΑΛΙΣΤΗΡΙΑ, ΜΙΣΘΩΣΕΙΣ)
    # =====================================================================
    if not payments_df.empty:
        for _, pay in payments_df[payments_df['Status'] == 'Εκκρεμεί'].iterrows():
            pay_id = str(pay.get("Payment_ID", ""))
            notif_type = f"DEBT_{pay_id}"
            if not notif_df.empty and not notif_df[notif_df["Type"] == notif_type].empty: continue
                
            l_id, p_type = str(pay.get("Lease_ID", "")), str(pay.get("Payment_Type", ""))
            amt = pd.to_numeric(str(pay.get("Amount", "0")).replace(',', '.'), errors='coerce')
            
            tenant_name, tenant_phone, tenant_email = "Ενοικιαστή", "", ""
            l_match = leases_df[leases_df['Lease_ID'] == l_id] if not leases_df.empty else pd.DataFrame()
            if not l_match.empty:
                t_ids = [t.strip() for t in str(l_match.iloc[0].get("Tenant_ID", "")).split(',') if t.strip()]
                if t_ids and not tenants_df.empty:
                    t_match = tenants_df[tenants_df["Tenant_ID"] == t_ids[0]]
                    if not t_match.empty:
                        tenant_name = f"{str(t_match.iloc[0].get('Επώνυμο', ''))} {str(t_match.iloc[0].get('Όνομα', ''))}".strip()
                        tenant_phone = str(t_match.iloc[0].get('Κινητό', '')).replace('nan', '')
                        tenant_email = str(t_match.iloc[0].get('Email', '')).replace('nan', '')
                
            m_str, y_str = str(pay.get("Calc_Month", "")), str(pay.get("Calc_Year", ""))
            period = f"του {m_str}/{y_str}" if m_str != "0" else "που έχει καταχωρηθεί"
            msg = f"Αγαπητέ/ή {tenant_name},\n\nΣας υπενθυμίζουμε ότι υπάρχει μια εκκρεμής οφειλή {amt:.2f}€ για {p_type} ({period}).\n\nΠαρακαλούμε μεριμνήστε για την τακτοποίησή της.\nΜε εκτίμηση."
            
            pending_notifications.append({"title": f"💰 Οφειλή ({p_type}: {amt:.2f}€)", "name": tenant_name, "phone": tenant_phone, "email": tenant_email, "message": msg, "type": notif_type, "css": "notif-debt", "entity": "Λογαριασμός"})

    if not insurances_df.empty:
        for _, ins in insurances_df.iterrows():
            try: ren_d = datetime.strptime(str(ins.get("Renewal_Date", "")), "%Y-%m-%d").date()
            except: continue
            days_left = (ren_d - today).days
            if days_left in [15, 7, 2]:
                notif_type = f"INS_{days_left}_{str(ins.get('Insurance_ID', ''))}"
                if not notif_df.empty and not notif_df[notif_df["Type"] == notif_type].empty: continue
                
                p_id, comp = str(ins.get("Property_ID", "")), str(ins.get("Company", ""))
                p_match = properties_df[properties_df["Property_ID"] == p_id] if not properties_df.empty else pd.DataFrame()
                owner_name, prop_charact = "Ιδιοκτήτη", "Ακίνητο"
                if not p_match.empty:
                    prop_charact = str(p_match.iloc[0].get("Χαρακτηριστικό", "Ακίνητο"))
                    owner_name = f"{str(p_match.iloc[0].get('Name_1', ''))} {str(p_match.iloc[0].get('Surname_1', ''))}".strip()

                msg = f"Γεια σας {owner_name},\n\nΥπενθύμιση: Το ασφαλιστήριο συμβόλαιο για το ακίνητο '{prop_charact}' στην {comp} λήγει σε {days_left} ημέρες ({ren_d.strftime('%d/%m/%Y')}).\n\nΠαρακαλώ μεριμνήστε για την ανανέωσή του.\nΜε εκτίμηση."
                pending_notifications.append({"title": f"🛡️ Λήξη σε {days_left} μέρες", "name": owner_name, "phone": "", "email": "", "message": msg, "type": notif_type, "css": "notif-danger" if days_left==2 else "notif-warning", "entity": prop_charact})

    if not leases_df.empty:
        for _, lease in leases_df.iterrows():
            try: end_d = datetime.strptime(str(lease.get("End_Date", "")), "%Y-%m-%d").date()
            except: continue
            days_left = (end_d - today).days
            if days_left in [30, 10]:
                notif_type = f"LEASE_{days_left}_{str(lease.get('Lease_ID', ''))}"
                if not notif_df.empty and not notif_df[notif_df["Type"] == notif_type].empty: continue
                
                p_id = str(lease.get("Property_ID", ""))
                p_match = properties_df[properties_df["Property_ID"] == p_id] if not properties_df.empty else pd.DataFrame()
                prop_charact = str(p_match.iloc[0].get("Χαρακτηριστικό", "Ακίνητο")) if not p_match.empty else "Ακίνητο"
                
                t_ids = [t.strip() for t in str(lease.get("Tenant_ID", "")).split(',') if t.strip()]
                tenant_name, tenant_phone, tenant_email = "Ενοικιαστή", "", ""
                if t_ids and not tenants_df.empty:
                    t_match = tenants_df[tenants_df["Tenant_ID"] == t_ids[0]]
                    if not t_match.empty:
                        tenant_name = f"{str(t_match.iloc[0].get('Επώνυμο', ''))} {str(t_match.iloc[0].get('Όνομα', ''))}".strip()
                        tenant_phone = str(t_match.iloc[0].get('Κινητό', '')).replace('nan', '')
                        tenant_email = str(t_match.iloc[0].get('Email', '')).replace('nan', '')

                msg = f"Αγαπητέ/ή {tenant_name},\n\nΣας ενημερώνουμε ότι το μισθωτήριο συμβόλαιο για το ακίνητο '{prop_charact}' λήγει σε {days_left} ημέρες ({end_d.strftime('%d/%m/%Y')}).\n\nΠαρακαλούμε επικοινωνήστε μαζί μας το συντομότερο.\nΜε εκτίμηση."
                pending_notifications.append({"title": f"📝 Λήξη σε {days_left} μέρες", "name": tenant_name, "phone": tenant_phone, "email": tenant_email, "message": msg, "type": notif_type, "css": "notif-warning" if days_left==10 else "", "entity": prop_charact})

    # =====================================================================
    # 3. ΕΜΦΑΝΙΣΗ ΚΑΙ ΕΠΕΞΕΡΓΑΣΙΑ ΑΥΤΟΜΑΤΩΝ ΕΙΔΟΠΟΙΗΣΕΩΝ
    # =====================================================================
    if not pending_notifications:
        st.success("🎉 Δεν υπάρχουν εκκρεμείς αυτόματες ειδοποιήσεις για σήμερα!")
        return

    st.write(f"Βρέθηκαν **{len(pending_notifications)}** αυτόματες εκκρεμότητες:")

    for idx, notif in enumerate(pending_notifications):
        with st.container(border=True):
            st.markdown(f"#### {notif['title']} - {notif['entity']}")
            st.caption(f"📍 Παραλήπτης: **{notif['name']}** | 📞 {notif['phone'] or '---'} | ✉️ {notif['email'] or '---'}")
            
            # TEXT AREA ΓΙΑ ΝΑ ΤΟ ΕΠΕΞΕΡΓΑΖΕΣΑΙ ΖΩΝΤΑΝΑ
            edited_msg = st.text_area("Κείμενο προς αποστολή:", value=notif['message'], height=120, key=f"txt_{notif['type']}")
            
            encoded_msg = urllib.parse.quote(edited_msg)
            clean_phone = str(notif["phone"]).replace(' ', '')
            if clean_phone and not clean_phone.startswith('+30') and not clean_phone.startswith('0030'): clean_phone = f"+30{clean_phone}"

            sms_link = f"sms:{clean_phone}?body={encoded_msg}" if clean_phone else "#"
            viber_link = f"viber://chat?number={clean_phone}" if clean_phone else "#"
            wa_link = f"https://wa.me/{clean_phone.replace('+','')}?text={encoded_msg}" if clean_phone else "#"
            
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f'<a href="{viber_link}" class="link-btn btn-viber" target="_blank" style="width:100%;">💜 Viber</a>', unsafe_allow_html=True)
            c2.markdown(f'<a href="{wa_link}" class="link-btn btn-wa" target="_blank" style="width:100%;">💬 WhatsApp</a>', unsafe_allow_html=True)
            c3.markdown(f'<a href="{sms_link}" class="link-btn btn-sms" target="_blank" style="width:100%;">📱 SMS App</a>', unsafe_allow_html=True)
            
            if c4.button("📧 Άμεση Αποστολή Email", type="primary", use_container_width=True, key=f"em_{notif['type']}"):
                if notif['email']:
                    success, res = send_direct_email(notif['email'], "Ενημέρωση από Property Management", edited_msg)
                    if success: st.success(res)
                    else: st.error(res)
                else: st.warning("Δεν υπάρχει καταχωρημένο Email.")
                
            if st.button(f"✅ Ολοκληρώθηκε (Απόκρυψη από τη λίστα)", use_container_width=True, key=f"done_{notif['type']}"):
                try:
                    log_id = f"LOG-{uuid.uuid4().hex[:6].upper()}"
                    gsheets_service.add_notification_log([log_id, today.strftime("%Y-%m-%d"), notif['name'], notif['type'], edited_msg])
                    st.success("Καταγράφηκε!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e: st.error(f"Σφάλμα καταγραφής: {e}")
