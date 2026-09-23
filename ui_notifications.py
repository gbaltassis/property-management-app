import streamlit as st
import pandas as pd
import gsheets_service
from datetime import datetime, date
import uuid
import urllib.parse
import time

COMMON_CSS = """
<style>
    .notif-card {
        background-color: #ffffff; border-left: 5px solid #007bff; border-radius: 6px; 
        padding: 15px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .notif-warning { border-left-color: #ffc107; }
    .notif-danger { border-left-color: #dc3545; }
    .notif-title { font-size: 16px; font-weight: bold; color: #31333F; margin-bottom: 5px; }
    .notif-text { font-size: 13px; color: #555; margin-bottom: 10px; background-color: #f8f9fa; padding: 10px; border-radius: 4px; }
    .notif-meta { font-size: 11px; color: #888; margin-bottom: 10px; }
    .link-btn {
        display: inline-block; padding: 6px 12px; margin-right: 5px; margin-bottom: 5px;
        border-radius: 4px; text-decoration: none; font-size: 12px; font-weight: bold; color: white !important;
        text-align: center; cursor: pointer; transition: opacity 0.2s;
    }
    .link-btn:hover { opacity: 0.8; }
    .btn-sms { background-color: #28a745; }
    .btn-viber { background-color: #665CAC; }
    .btn-email { background-color: #ea4335; }
</style>
"""

def show():
    st.markdown(COMMON_CSS, unsafe_allow_html=True)
    st.header("🔔 Κέντρο Ειδοποιήσεων")
    st.caption("Εκκρεμείς ειδοποιήσεις για ανανεώσεις συμβολαίων και ασφαλιστηρίων.")

    try:
        leases_df = gsheets_service.fetch_all_leases()
        insurances_df = gsheets_service.fetch_all_insurances()
        properties_df = gsheets_service.fetch_all_properties()
        tenants_df = gsheets_service.fetch_all_tenants()
        
        try: notif_df = gsheets_service.fetch_all_notifications()
        except: notif_df = pd.DataFrame(columns=["Log_ID", "Date_Sent", "Target", "Type", "Message"])
    except Exception as e:
        st.error(f"Αδυναμία φόρτωσης δεδομένων: {e}")
        return

    today = date.today()
    pending_notifications = []

    # --- 1. ΕΛΕΓΧΟΣ ΑΣΦΑΛΙΣΤΗΡΙΩΝ (15, 7, 2 ΜΕΡΕΣ ΠΡΙΝ) ---
    if not insurances_df.empty:
        for _, ins in insurances_df.iterrows():
            try: ren_d = datetime.strptime(str(ins.get("Renewal_Date", "")), "%Y-%m-%d").date()
            except: continue
            
            days_left = (ren_d - today).days
            
            if days_left in [15, 7, 2]:
                i_id = str(ins.get("Insurance_ID", ""))
                p_id = str(ins.get("Property_ID", ""))
                comp = str(ins.get("Company", ""))
                
                # Εύρεση Ιδιοκτήτη (Στέλνουμε στον 1ο Ιδιοκτήτη του Ακινήτου)
                p_match = properties_df[properties_df["Property_ID"] == p_id] if not properties_df.empty else pd.DataFrame()
                owner_name = "Ιδιοκτήτη"
                prop_charact = "Ακίνητο"
                if not p_match.empty:
                    prop_charact = str(p_match.iloc[0].get("Χαρακτηριστικό", "Ακίνητο"))
                    owner_name = f"{str(p_match.iloc[0].get('Name_1', ''))} {str(p_match.iloc[0].get('Surname_1', ''))}".strip()

                notif_type = f"INS_{days_left}_{i_id}"
                
                # Έλεγχος αν έχει ήδη σταλεί
                if not notif_df.empty and not notif_df[notif_df["Type"] == notif_type].empty:
                    continue
                
                msg = (f"Γεια σας {owner_name},\n\n"
                       f"Υπενθύμιση: Το ασφαλιστήριο συμβόλαιο για το ακίνητο '{prop_charact}' "
                       f"στην εταιρεία {comp} λήγει σε {days_left} ημέρες ({ren_d.strftime('%d/%m/%Y')}).\n\n"
                       f"Παρακαλώ μεριμνήστε για την ανανέωσή του.\nΜε εκτίμηση.")
                
                urgency_class = "notif-danger" if days_left == 2 else ("notif-warning" if days_left == 7 else "")
                
                pending_notifications.append({
                    "title": f"🛡️ Λήξη Ασφαλιστηρίου σε {days_left} μέρες",
                    "target_name": owner_name,
                    "target_phone": "", # Ο διαχειριστής θα βάλει το νούμερο του ιδιοκτήτη
                    "target_email": "",
                    "message": msg,
                    "type": notif_type,
                    "css_class": urgency_class,
                    "entity": prop_charact
                })

    # --- 2. ΕΛΕΓΧΟΣ ΜΙΣΘΩΣΕΩΝ (30, 10 ΜΕΡΕΣ ΠΡΙΝ) ---
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
                
                # Παίρνουμε τον πρώτο ενοικιαστή για τα στοιχεία επικοινωνίας
                tenant_name, tenant_phone, tenant_email = "Ενοικιαστή", "", ""
                if t_ids and not tenants_df.empty:
                    t_match = tenants_df[tenants_df["Tenant_ID"] == t_ids[0]]
                    if not t_match.empty:
                        tenant_name = f"{str(t_match.iloc[0].get('Επώνυμο', ''))} {str(t_match.iloc[0].get('Όνομα', ''))}".strip()
                        tenant_phone = str(t_match.iloc[0].get('Κινητό', '')).replace('nan', '')
                        tenant_email = str(t_match.iloc[0].get('Email', '')).replace('nan', '')

                notif_type = f"LEASE_{days_left}_{l_id}"
                
                if not notif_df.empty and not notif_df[notif_df["Type"] == notif_type].empty:
                    continue
                
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

    # --- ΕΜΦΑΝΙΣΗ ΕΙΔΟΠΟΙΗΣΕΩΝ ΣΤΟ UI ---
    if not pending_notifications:
        st.success("🎉 Δεν υπάρχουν εκκρεμείς ειδοποιήσεις για σήμερα!")
        return

    st.write(f"Βρέθηκαν **{len(pending_notifications)}** εκκρεμείς ειδοποιήσεις:")

    for notif in pending_notifications:
        encoded_msg = urllib.parse.quote(notif["message"])
        
        # Καθαρισμός τηλεφώνου για το URL (π.χ. αφαίρεση κενών)
        clean_phone = str(notif["target_phone"]).replace(' ', '')
        if clean_phone and not clean_phone.startswith('+30'):
            clean_phone = f"+30{clean_phone}"

        sms_link = f"sms:{clean_phone}?body={encoded_msg}" if clean_phone else f"sms:?body={encoded_msg}"
        viber_link = f"viber://chat?number={clean_phone}" if clean_phone else "#"
        email_link = f"mailto:{notif['target_email']}?subject=Ενημέρωση από Property Management&body={encoded_msg}" if notif["target_email"] else "#"

        st.markdown(f"""
            <div class="notif-card {notif['css_class']}">
                <div class="notif-title">{notif['title']} - {notif['entity']}</div>
                <div class="notif-meta">📍 Παραλήπτης: <b>{notif['target_name']}</b> | 📞 {notif['target_phone'] or 'Δεν έχει καταχωρηθεί'} | ✉️ {notif['target_email'] or 'Δεν έχει καταχωρηθεί'}</div>
                <div class="notif-text">{notif['message'].replace(chr(10), '<br>')}</div>
                <div>
                    <a href="{sms_link}" class="link-btn btn-sms" target="_blank">📱 Αποστολή SMS</a>
                    <a href="{viber_link}" class="link-btn btn-viber" target="_blank">💜 Άνοιγμα Viber</a>
                    <a href="{email_link}" class="link-btn btn-email" target="_blank">📧 Αποστολή Email</a>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        if st.button(f"✅ Επιβεβαίωση Αποστολής", key=f"btn_{notif['type']}"):
            try:
                log_id = f"LOG-{uuid.uuid4().hex[:6].upper()}"
                gsheets_service.add_notification_log([log_id, today.strftime("%Y-%m-%d"), notif['target_name'], notif['type'], notif['message']])
                st.success("Η ειδοποίηση καταγράφηκε ως 'Σταλμένη'!")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Σφάλμα καταγραφής: {e}")
