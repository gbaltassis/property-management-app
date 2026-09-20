import requests
import json
import streamlit as st

def send_macrodroid_alert(payload):
    """
    Αποστέλλει ένα JSON payload στο Webhook URL του MacroDroid.
    Το payload περιέχει δεδομένα όπως όνομα, ημ/νια λήξης κ.λπ.
    """
    
    # ΠΡΟΣΟΧΗ: Πρέπει να αντικαταστήσεις αυτό το URL με το δικό σου 
    # Device ID και το όνομα του Event που ρύθμισες στο MacroDroid.
    # Παράδειγμα: "https://trigger.macrodroid.com/1a2b3c4d-5e6f/lease_warning"
    MACRODROID_WEBHOOK_URL = "https://trigger.macrodroid.com/YOUR_DEVICE_ID_HERE/YOUR_EVENT_NAME"
    
    try:
        # Ορίζουμε ότι στέλνουμε δεδομένα τύπου JSON
        headers = {'Content-Type': 'application/json'}
        
        # Εκτέλεση του POST request (Αποστολή)
        response = requests.post(MACRODROID_WEBHOOK_URL, data=json.dumps(payload), headers=headers)
        
        # Αν η απάντηση του server είναι 200 (Επιτυχία), επιστρέφουμε True
        if response.status_code == 200:
            return True
        else:
            # Αν υπάρχει σφάλμα, εκτυπώνουμε τον κωδικό σφάλματος στην κονσόλα για troubleshooting
            print(f"Αποτυχία MacroDroid. Κωδικός HTTP: {response.status_code}, Μήνυμα: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        # Πιάνει περιπτώσεις όπου δεν υπάρχει καν ίντερνετ ή το URL είναι λάθος
        print(f"Σφάλμα σύνδεσης με MacroDroid: {e}")
        return False
