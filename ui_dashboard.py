import streamlit as st
import gsheets_service
import pandas as pd
from datetime import datetime
import notification_service  # Θα το φτιάξουμε αμέσως μετά

def show():
    st.header("Επισκόπηση & Ειδοποιήσεις")
    
    # 1. Φόρτωση δεδομένων
    try:
        leases_df = gsheets_service.fetch_all_leases()
        properties_df = gsheets_service.fetch_all_properties()
        tenants_df = gsheets_service.fetch_all_tenants()
    except Exception as e:
        st.error("Αδυναμία φόρτωσης δεδομένων.")
        return

    # Αν δεν υπάρχουν δεδομένα, σταματάμε εδώ
    if leases_df.empty:
        st.info("Το μητρώο είναι άδειο. Προσθέστε ακίνητα, ενοικιαστές και μισθώσεις για να δείτε στατιστικά.")
        return

    # 2. Βασικά Στατιστικά (KPIs)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="Σύνολο Ακινήτων", value=len(properties_df))
    with col2:
        st.metric(label="Ενεργές Μισθώσεις", value=len(leases_df))
    with col3:
        # Υπολογισμός συνολικού μηνιαίου εισοδήματος
        # Προσπαθούμε να μετατρέψουμε τη στήλη σε αριθμούς, αγνοώντας τυχόν λάθη
        leases_df['Monthly_Rent'] = pd.to_numeric(leases_df['Monthly_Rent'], errors='coerce').fillna(0)
        total_rent = leases_df['Monthly_Rent'].sum()
        st.metric(label="Συνολικό Ενοίκιο", value=f"{total_rent:,.2f} €")

    st.divider()

    # 3. Έλεγχος Λήξης Μισθώσεων
    st.subheader("⚠️ Επερχόμενες Λήξεις Μισθώσεων")
    
    today = datetime.today()
    expiring_soon_count = 0
    
    # Μετατροπή της στήλης End_Date σε μορφή ημερομηνίας
    leases_df['End_Date_Obj'] = pd.to_datetime(leases_df['End_Date'], errors='coerce')
    
    # Εντοπισμός των μισθώσεων που λήγουν σε λιγότερο από 60 μέρες
    for index, row in leases_df.iterrows():
        end_date = row['End_Date_Obj']
        
        # Αν η ημερομηνία είναι έγκυρη
        if pd.notnull(end_date):
            days_remaining = (end_date - today).days
            
            if days_remaining <= 60:
                expiring_soon_count += 1
                
                # Βρίσκουμε το όνομα του ενοικιαστή και τη διεύθυνση του ακινήτου για να τα εμφανίσουμε όμορφα
                tenant_match = tenants_df[tenants_df["Tenant_ID"] == row["Tenant_ID"]]
                tenant_name = f"{tenant_match.iloc[0]['Όνομα']} {tenant_match.iloc[0]['Επώνυμο']}" if not tenant_match.empty else "Άγνωστος"
                
                prop_match = properties_df[properties_df["Property_ID"] == row["Property_ID"]]
                prop_address = f"{prop_match.iloc[0]['Διεύθυνση']} {prop_match.iloc[0]['Αριθμός']}" if not prop_match.empty else "Άγνωστο"
                
                # Εμφάνιση της ειδοποίησης (Κόκκινη αν έχει ήδη λήξει, Πορτοκαλί αν λήγει σύντομα)
                if days_remaining < 0:
                    st.error(f"**ΕΛΗΞΕ ΠΡΙΝ {-days_remaining} ΜΕΡΕΣ:** Ακίνητο: {prop_address} | Ενοικιαστής: {tenant_name} | Ημ/νία Λήξης: {row['End_Date']}")
                else:
                    st.warning(f"**ΛΗΓΕΙ ΣΕ {days_remaining} ΜΕΡΕΣ:** Ακίνητο: {prop_address} | Ενοικιαστής: {tenant_name} | Ημ/νία Λήξης: {row['End_Date']}")
                
                # Κουμπί για αποστολή ειδοποίησης μέσω MacroDroid
                # Χρησιμοποιούμε st.button με key για να μην μπερδεύονται τα κουμπιά αν υπάρχουν πολλές λήξεις
                if st.button(f"📲 Αποστολή Ειδοποίησης (Viber/SMS) σε {tenant_name}", key=f"btn_{row['Lease_ID']}"):
                    with st.spinner("Αποστολή ειδοποίησης..."):
                        # Εδώ καλούμε το notification_service
                        payload = {
                            "tenant_name": tenant_name,
                            "property_address": prop_address,
                            "end_date": row['End_Date'],
                            "days_remaining": days_remaining,
                            "message_type": "lease_expiration_warning"
                        }
                        
                        success = notification_service.send_macrodroid_alert(payload)
                        
                        if success:
                            st.success("Το μήνυμα στάλθηκε επιτυχώς στο MacroDroid!")
                        else:
                            st.error("Αποτυχία αποστολής. Ελέγξτε τις ρυθμίσεις του Webhook στο MacroDroid.")

    if expiring_soon_count == 0:
        st.success("Καμία μίσθωση δεν λήγει τις επόμενες 60 ημέρες. Όλα βαίνουν καλώς! 🌿")
