import streamlit as st
# Εισαγωγή των υπόλοιπων αρχείων-ενοτήτων
import ui_dashboard
import ui_leases
import ui_payments
import ui_registry

# Ρύθμιση της σελίδας - ΜΙΑ ΚΑΙ ΜΟΝΑΔΙΚΗ ΦΟΡΑ
st.set_page_config(
    page_title="Διαχείριση Ακινήτων", 
    page_icon="🏢", 
    layout="wide",  # <--- Αυτό κάνει την εφαρμογή να απλώνεται σε όλη την οθόνη (Desktop)
    initial_sidebar_state="collapsed"
)

# Τίτλος της εφαρμογής
st.title("Διαχείριση Ακινήτων")

# Δημιουργία των 4 βασικών καρτελών (Tabs)
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Dashboard", 
    "📝 Μισθώσεις", 
    "💰 Πληρωμές", 
    "⚙️ Μητρώο"
])

# Περιεχόμενο κάθε καρτέλας
with tab1:
    ui_dashboard.show()

with tab2:
    ui_leases.show()

with tab3:
    ui_payments.show()

with tab4:
    ui_registry.show()
