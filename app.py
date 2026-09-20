import streamlit as st

# Ρύθμιση της σελίδας - ΠΡΕΠΕΙ να είναι η πρώτη εντολή Streamlit στο αρχείο
st.set_page_config(
    page_title="Property Manager", 
    page_icon="🏢", 
    layout="centered",
    initial_sidebar_state="collapsed" # Κρύβουμε το sidebar για καλύτερη εμπειρία σε κινητό
)

# Εισαγωγή των υπόλοιπων αρχείων-ενοτήτων
import ui_dashboard
import ui_leases
import ui_payments
import ui_registry

# Τίτλος της εφαρμογής
st.title("Διαχείριση Ακινήτων")

# Δημιουργία των 4 βασικών καρτελών (Tabs)
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Dashboard", 
    "📝 Μισθώσεις", 
    "💰 Πληρωμές", 
    "⚙️ Μητρώο"
])

# Περιεχόμενο κάθε καρτέλας - Εδώ καλούμε τις συναρτήσεις από τα άλλα αρχεία
with tab1:
    ui_dashboard.show()

with tab2:
    ui_leases.show()

with tab3:
    ui_payments.show()

with tab4:
    ui_registry.show()
