#!/usr/bin/env python3
import os
import streamlit as st
import oracledb
import pandas as pd
from io import BytesIO

from dotenv import load_dotenv
load_dotenv()

ora_user = os.getenv('DB_USER')
ora_pass = os.getenv('DB_PASS')
ora_host = os.getenv('DB_HOST')
ora_port = os.getenv('DB_PORT', '1521')
ora_service_name = os.getenv('DB_SERVICE')

# Function to connect to Oracle
def get_connection():
    dsn = f"(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST={ora_host})(PORT={ora_port}))(CONNECT_DATA=(SERVICE_NAME={ora_service_name})))"
    return oracledb.connect(user=ora_user, password=ora_pass, dsn=dsn, mode=oracledb.DEFAULT_AUTH)


# Streamlit UI
st.set_page_config(page_title="Customer Statement Portal", layout="wide")
st.title("Customer Statement Portal")
# st.title("📄 Customer Statement Portal")

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["🔍 Search", "📊 Summary", "📥 Export", "❓ Help"])

with tab1:
    st.subheader("🔍 Search Customer Statement")

    # Side-by-side layout
    col1, col2, col3 = st.columns([1.5, 3, 1])
    with col1:
        search_type = st.radio("Search by:", ["Policy ID", "Customer Name"], label_visibility="visible")
    with col2:
        search_value = st.text_input("Enter search value", placeholder="e.g. G/001/07/3005/2020/0007")
    with col3:
        st.write("")  # Spacer
        search_button = st.button("🔍 Search", use_container_width=True)

    # Optional filters
    with st.expander("📅 Filter by Document Date"):
        start_date = st.date_input("Start Date", value=None)
        end_date = st.date_input("End Date", value=None)

    # Warning for slower search
    if search_type == "Customer Name":
        st.warning("⚠️ Searching by Account Name may take longer than searching by Policy ID.")

    # Search logic
    if search_button:
        if not search_value:
            st.warning("Please enter a search value.")
        else:
            with st.spinner("🔄 Searching..."):
                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    if search_type == "Policy ID":
                        query = """SELECT * FROM BI_CUSTOMER_STATEMENT_VIEW 
                                   WHERE POLICY_NO = :1 
                                   ORDER BY document_date DESC"""
                        cursor.execute(query, [search_value.strip()])
                    else:
                        query = """SELECT * FROM BI_CUSTOMER_STATEMENT_VIEW 
                                   WHERE UPPER(TRIM(INSURED_NAME)) LIKE UPPER(:1) 
                                   ORDER BY document_date DESC"""
                        cursor.execute(query, [f"%{search_value.strip()}%"])

                    columns = [col[0] for col in cursor.description]
                    results = cursor.fetchall()

                    if results:
                        df = pd.DataFrame(results, columns=columns)

                        # Apply date filter
                        if 'DOCUMENT_DATE' in df.columns and start_date and end_date:
                            df['DOCUMENT_DATE'] = pd.to_datetime(df['DOCUMENT_DATE'])
                            df = df[(df['DOCUMENT_DATE'].dt.date >= start_date) & (df['DOCUMENT_DATE'].dt.date <= end_date)]

                        st.success(f"✅ Found {len(df)} record(s).")
                        st.dataframe(df)

                        # Summary tab
                        with tab2:
                            st.subheader("📊 Summary Statistics")
                            st.metric("Total Records", len(df))
                            if 'AMOUNT' in df.columns:
                                st.metric("Total Amount", f"{df['AMOUNT'].sum():,.2f}")

                        # Export tab
                        with tab3:
                            st.subheader("📥 Export Results")
                            output = BytesIO()
                            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                                df.to_excel(writer, index=False, sheet_name='Statements')
                            st.download_button("Download Excel File", data=output.getvalue(), file_name="customer_statements.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

                    else:
                        st.info("No records found.")

                    cursor.close()
                    conn.close()

                except oracledb.Error as err:
                    st.error(f"Database error: {err}")
                except Exception as e:
                    st.error(f"Unexpected error: {e}")

with tab4:
    st.subheader("❓ Help")
    st.markdown("""
    - **Policy ID**: Use the exact policy number for faster results.
    - **Customer Name**: Partial matches are allowed but may take longer.
    - **Document Date Filter**: Use the expander to narrow results by date.
    - **Export**: Download results as Excel for offline use.
    """)

# Call streamlit_watchdog.py