import streamlit as st
import gsheets_service
import pandas as pd
from datetime import date, datetime
import requests
import time
import uuid
import streamlit.components.v1 as components

COMMON_CSS = """
<style>
    html, body { font-family: sans-serif; background-color: transparent; }
    .notif-card { background-color: #f8f9fa; border-left: 4px solid #007bff; border-radius: 8px; padding: 15px; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); display: flex; flex-direction: column; justify-content: space-between; }
    .notif-urgent { border-left-color: #dc3545; background-color: #fff3cd; }
    .notif-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }
    .notif-title { font-weight: bold; color: #31333F; font-size: 15px; }
    .notif-target { font-size: 12px; color: #6c757d; background: #e9ecef; padding: 2px 6px; border-radius: 4px; }
    .notif-text { font-size: 14px; color: #444; margin-bottom: 15px; line-height: 1.4; background: white; padding: 10px; border-radius: 4px; border: 1px dashed #ccc; }
    
    .btn-sms { background-color: #28a745; color: white; border: none; padding: 8px 12px; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: bold; width: 100%; text-align: center; transition: background-color 0.2s; display: inline-block; text-decoration: none; }
    .btn-sms:hover { background-color: #218838; color: white; }
    .btn-sms:disabled { background-color: #6c757d; cursor: not-allowed; }
    
    @media (prefers-color-scheme: dark) {
        .notif-card { background-color: #1e2127; border-left-color: #3b82f6; box-shadow: 0 1px 3px rgba(0,0,0,0.3); }
        .notif-urgent { border-left-color: #ef4444; background-color: #2e1c1c; }
        .notif-title { color: #f8f9fa; }
        .notif-target { background: #2d3748; color: #a0aec0; }
        .notif-text { color: #e2e8f0; background: #1a202c; border-color: #4a5568; }
    }
</style>
"""

# Διαβάζουμε το Webhook URL από τα Secrets του Streamlit (π.χ. st.secrets["macrodroid_url"])
MACRODROID_URL = st.secrets.get("macrodroid_url", "")

def send_sms_via_macrodroid(phone, message):
    if not MACRODROID_URL:
        st.error("Σφάλμα: Δεν έχει οριστεί το 'macrodroid_url' στα Secrets!")
        return False
    
    try:
        # Το Webhook του MacroDroid περιμένει GET (ή POST) request με τα params number & message
        response = requests.get(MACRODROID_URL, params={"number": phone, "message": message}, timeout=10)
        
        # Αν το MacroDroid Webhook επιστρέψει 200 (OK), σημαίνει ότι έφτασε στο κινητό σου!
        if response.status_code == 200:
            return True
        else:
            st.error(f"Το MacroDroid επέστρεψε σφάλμα: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        st.error(f"Αποτυχία επικοινωνίας με το MacroDroid: {e}")
        return False

def show():
    st.markdown(COMMON_CSS, unsafe_allow_html=True)
    st.header("🔔 Κέντρο Ειδοποιήσεων")
    st.caption("Το σύστημα ανιχνεύει αυτόματα τις επερχόμενες λήξεις και προτείνει μηνύματα (SMS).")

    if not MACRODROID_URL:
        st.warning("⚠️ Δεν έχει ρυθμιστεί το Webhook του MacroDroid. Η αποστολή SMS δεν θα λειτουργήσει.")

    try:
        leases_df = gsheets_service.fetch_all_leases()
        insurances_df = gsheets_service.fetch_all_insurances()
        properties_df = gsheets_service.fetch_all_properties()
        tenants_df = gsheets_service.fetch_all_tenants()
        
        # Προσπαθούμε να διαβάσουμε το Log (για να μην στέλνουμε διπλά μηνύματα)
        try:
            log_df = gsheets_service.fetch_all_notifications_log()
        except:
            # Αν δεν υπάρχει το φύλλο ή είναι άδειο, φτιάχνουμε ένα κενό DataFrame
            log_df = pd.DataFrame(columns=["Log_ID", "Date_Sent", "Target", "Type", "Message"])
            
    except Exception as e:
        st.error(f"Σφάλμα κατά τη φόρτωση δεδομένων: {e}")
        return

    today = date.today()
    pending_notifications = []

    # =============================================================
    # 1. ΕΛΕΓΧΟΣ ΜΙΣΘΩΣΕΩΝ (30 & 10 μέρες πριν τη λήξη)
    # =============================================================
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
                        t_phone = str(t_match.iloc[0].get("Κινητό", ""))
                        
                        # Μοναδικό αναγνωριστικό για αυτό το μήνυμα, για να το ψάξουμε στο Log
                        notif_type = f"LEASE_{days_left}_{l_id}_{t_id}"
                        
                        # Έλεγχος αν έχει ήδη σταλεί (στο Log)
                        already_sent = False
                        if not log_df.empty and 'Type' in log_df.columns:
                            already_sent = not log_df[log_df['Type'] == notif_type].empty
                        
                        # Αν δεν έχει σταλεί και έχει τηλέφωνο, το προτείνουμε!
                        if not already_sent and t_phone and t_phone != 'nan':
                            msg = f"Γεια σας {t_name}. Σας υπενθυμίζουμε ότι το μισθωτήριο για το ακίνητο '{p_name}' λήγει σε {days_left} ημέρες ({end_d.strftime('%d/%m/%Y')}). Παρακαλούμε επικοινωνήστε μαζί μας."
                            pending_notifications.append({
                                "Type": notif_type, "Target_Phone": t_phone, "Target_Name": t_name, 
                                "Title": f"Λήξη Μίσθωσης σε {days_left} μέρες ({p_name})", "Message": msg, "Urgent": days_left == 10
                            })

    # =============================================================
    # 2. ΕΛΕΓΧΟΣ ΑΣΦΑΛΙΣΤΗΡΙΩΝ (15, 7 & 2 μέρες πριν τη λήξη)
    # =============================================================
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
                
                # --- ΣΗΜΑΝΤΙΚΟ ---
                # Στο Μητρώο δεν καταγράφουμε (ακόμα) το κινητό του Ιδιοκτήτη. 
                # Οπότε για τα ασφαλιστήρια, βάζουμε τον ΔΙΚΟ ΣΟΥ αριθμό για να έρχεται η ειδοποίηση σε σένα!
                # Άλλαξε το '6900000000' με το δικό σου νούμερο:
                owner_phone = "6900000000" 
                
                notif_type = f"INS_{days_left}_{i_id}"
                
                already_sent = False
                if not log_df.empty and 'Type' in log_df.columns:
                    already_sent = not log_df[log_df['Type'] == notif_type].empty
                
                if not already_sent:
                    msg = f"Υπενθύμιση (Διαχείριση): Το ασφαλιστήριο ({ins.get('Category')}) για '{p_name}' λήγει σε {days_left} ημέρες ({ren_d.strftime('%d/%m/%Y')})."
                    pending_notifications.append({
                        "Type": notif_type, "Target_Phone": owner_phone, "Target_Name": "Ιδιοκτήτης / Διαχειριστής", 
                        "Title": f"Λήξη Ασφαλιστηρίου σε {days_left} μέρες ({p_name})", "Message": msg, "Urgent": days_left <= 7
                    })

    # =============================================================
    # ΟΠΤΙΚΟΠΟΙΗΣΗ (RENDER) ΕΙΔΟΠΟΙΗΣΕΩΝ ΣΤΟ STREAMLIT
    # =============================================================
    st.markdown("---")
    
    if not pending_notifications:
        st.success("🎉 Όλα υπό έλεγχο! Δεν υπάρχουν εκκρεμείς ειδοποιήσεις για σήμερα.")
    else:
        st.warning(f"Έχετε {len(pending_notifications)} ειδοποιήσεις προς αποστολή.")
        
        # Εμφανίζουμε κάθε ειδοποίηση σε δική της κάρτα
        for idx, notif in enumerate(pending_notifications):
            urgency_class = "notif-urgent" if notif["Urgent"] else ""
            
            with st.container():
                st.markdown(f"""
                <div class="notif-card {urgency_class}">
                    <div class="notif-header">
                        <div class="notif-title">{notif['Title']}</div>
                        <div class="notif-target">📱 {notif['Target_Name']} ({notif['Target_Phone']})</div>
                    </div>
                    <div class="notif-text">{notif['Message']}</div>
                </div>
                """, unsafe_allow_html=True)
                
                # Κουμπί Αποστολής: Μόλις πατηθεί, κάνει κλήση στο function
                if st.button(f"🚀 Αποστολή SMS", key=f"btn_send_{idx}", type="primary"):
                    with st.spinner("Επικοινωνία με το κινητό σας..."):
                        success = send_sms_via_macrodroid(notif["Target_Phone"], notif["Message"])
                        
                        if success:
                            try:
                                # Αν στάλθηκε, το γράφουμε στο Sheets Log για να μην ξαναβγεί!
                                log_id = f"LOG-{uuid.uuid4().hex[:6].upper()}"
                                gsheets_service.add_notification_log([
                                    log_id, 
                                    today.strftime("%Y-%m-%d"), 
                                    notif["Target_Name"], 
                                    notif["Type"], 
                                    notif["Message"]
                                ])
                                st.success("Το SMS προωθήθηκε στο κινητό σας!")
                                time.sleep(1.5)
                                st.rerun() # Κάνει refresh τη σελίδα για να εξαφανιστεί η ειδοποίηση!
                            except Exception as e:
                                st.error(f"Το SMS στάλθηκε, αλλά απέτυχε η καταγραφή στο Sheet: {e}")
