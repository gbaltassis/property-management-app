import streamlit as st
import ui_dashboard
import ui_leases
import ui_payments
import ui_registry
import ui_expenses # Το νέο μας αρχείο
import ui_reports
import ui_notifications

st.set_page_config(page_title="Διαχείριση Ακινήτων", page_icon="🏢", layout="wide", initial_sidebar_state="collapsed")
st.title("Διαχείριση Ακινήτων")

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["📊 Dashboard", "📝 Μισθώσεις", "💰 Εισπράξεις", "📉 Έξοδα", "⚙️ Μητρώο", "📈 Αναφορές", "🔔 Ειδοποιήσεις"])

with tab1: ui_dashboard.show()
with tab2: ui_leases.show()
with tab3: ui_payments.show()
with tab4: ui_expenses.show() # Καλεί το νέο αρχείο
with tab5: ui_registry.show()
with tab6: ui_reports.show()
with tab7: ui_notifications.show()
