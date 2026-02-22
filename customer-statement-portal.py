# !/usr/bin/env python3
# direct search from db, it is what it is

import os
from io import BytesIO
import streamlit as st
import oracledb
import pandas as pd

## PDF support
# try:
#     from reportlab.lib import colors
#     from reportlab.lib.pagesizes import A4, landscape
#     from reportlab.lib.styles import getSampleStyleSheet
#     from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
#     REPORTLAB_AVAILABLE = True
# except Exception:
#     REPORTLAB_AVAILABLE = False

from dotenv import load_dotenv
load_dotenv()

ora_user = os.getenv('DB_USER')
ora_pass = os.getenv('DB_PASS')
ora_host = os.getenv('DB_HOST')
ora_port = os.getenv('DB_PORT', '1521')
ora_service_name = os.getenv('DB_SERVICE')

# ---- Streamlit page config
st.set_page_config(
    page_title="Customer Statement Portal",
    page_icon="📄",
    layout="wide"
)

# st.markdown("""
#     <style>
#         /* Reduce top padding */
#         .block-container {
#             padding-top: 1rem;
#         }
#         /* Reduce space under titles */
#         h2 {
#             margin-bottom: 0.2rem !important;
#         }
#         /* Reduce space above divider */
#         hr {
#             margin-top: 0.5rem !important;
#         }
#     </style>
# """, unsafe_allow_html=True)

# Helpers
def get_connection():
    """Create an Oracle connection using DSN string."""
    dsn = (
        f"(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST={ora_host})(PORT={ora_port}))"
        f"(CONNECT_DATA=(SERVICE_NAME={ora_service_name})))"
    )
    return oracledb.connect(
        user=ora_user,
        password=ora_pass,
        dsn=dsn,
        mode=oracledb.DEFAULT_AUTH
    )

def export_df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")

def export_df_to_pdf_bytes(df: pd.DataFrame, title: str = "Customer Statements") -> bytes:
    """
    Create a simple landscape A4 PDF table from a DataFrame.
    Requires reportlab. If unavailable, raises RuntimeError.
    """
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("PDF export requires 'reportlab'. Install with: pip install reportlab")

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=18, rightMargin=18, topMargin=18, bottomMargin=18)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph(title, styles["Title"]))
    elements.append(Spacer(1, 8))

    # Convert DataFrame to table data
    data = [list(df.columns)] + df.astype(str).values.tolist()

    # Build table with minimal styling
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F3F6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111111")),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#DDDDDD")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#BBBBBB")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
    ]))
    elements.append(table)

    doc.build(elements)
    buf.seek(0)
    return buf.getvalue()

def render_welcome():
    """Shown before any search results—uses space effectively."""
    st.markdown(
        """
        ### Welcome to the Customer Statement Portal
        Use the search bar above to find statements by **Policy ID** or **Customer Name**.  
        - For fastest results, search by exact **Policy ID**  
        - For broader lookups, use **Customer Name** (supports partial matches but takes longer)
        """
    )


# UI Header
st.markdown("## XXXXX Customer Statement Portal")
# st.divider()

# Keep prior inputs between runs
if "search_type" not in st.session_state:
    st.session_state.search_type = "Policy ID"
if "search_value" not in st.session_state:
    st.session_state.search_value = ""

# Search Form (aligned on one row)
with st.form("search_form"):
    r1, r2, r3 = st.columns([3, 7, 2], vertical_alignment="bottom")
    with r1:
        search_type = st.radio(
            "Search by",
            ["Policy ID", "Customer Name"],
            index=0 if st.session_state.search_type == "Policy ID" else 1,
            horizontal=True,
        )
    with r2:
        search_value = st.text_input(
            "Enter search value",
            value=st.session_state.search_value,
            placeholder="G/001/01/1001/2025/0001",
        )
    with r3:
        st.write("")  # spacer to align button nicely with inputs
        submitted = st.form_submit_button("🔍 Search", use_container_width=True)
        # st.caption("Actions")  # or st.markdown("**Actions**")
        # submitted = st.form_submit_button("🔍 Search", use_container_width=True)


# Optional date filter
with st.expander("📅 Optional: Filter by Document Date"):
    use_date_filter = st.checkbox("Enable date filter", value=False)
    start_date = end_date = None
    if use_date_filter:
        d1, d2 = st.columns(2)
        with d1:
            start_date = st.date_input("Start date")
        with d2:
            end_date = st.date_input("End date")

# Guidance for slower search
if search_type == "Customer Name":
    st.info("ℹ️ Searching by **Customer Name** may take longer than an exact **Policy ID**.", icon="⏱️")


# Execute Search
df = None
if submitted:
    st.session_state.search_type = search_type
    st.session_state.search_value = search_value

    if not search_value or not search_value.strip():
        st.warning("Please enter a search value.")
    else:
        with st.spinner("🔄 Searching..."):
            conn = cursor = None
            try:
                conn = get_connection()
                cursor = conn.cursor()

                if search_type == "Policy ID":
                    query = """
                        SELECT * FROM BI_CUSTOMER_STATEMENT_VIEW
                        WHERE POLICY_NO = :1 
                        ORDER BY DOCUMENT_DATE DESC
                    """
                    cursor.execute(query, [search_value.strip()])
                else:
                    query = """
                        SELECT * FROM BI_CUSTOMER_STATEMENT_VIEW
                        WHERE UPPER(TRIM(INSURED_NAME)) LIKE UPPER(:1)
                        ORDER BY DOCUMENT_DATE DESC
                    """
                    cursor.execute(query, [f"%{search_value.strip()}%"])

                columns = [col[0] for col in cursor.description] if cursor.description else []
                results = cursor.fetchall()

                if results:
                    df = pd.DataFrame(results, columns=columns)

                    # Apply date filter if enabled and column exists
                    if use_date_filter and 'DOCUMENT_DATE' in df.columns and start_date and end_date:
                        df['DOCUMENT_DATE'] = pd.to_datetime(df['DOCUMENT_DATE'])
                        df = df[(df['DOCUMENT_DATE'].dt.date >= start_date) &
                                (df['DOCUMENT_DATE'].dt.date <= end_date)]

                    # After filtering, check emptiness
                    if df.empty:
                        st.info("No records match the selected date range.")
                    else:
                        st.success(f"✅ Found {len(df)} record(s).")

                        # KPI row
                        k1, k2, k3 = st.columns([2, 2, 6])
                        with k1:
                            st.metric("Total Records", len(df))
                        with k2:
                            if 'AMOUNT' in df.columns:
                                try:
                                    total_amount = pd.to_numeric(df['AMOUNT'], errors='coerce').fillna(0).sum()
                                    st.metric("Total Amount", f"{total_amount:,.2f}")
                                except Exception:
                                    st.metric("Total Amount", "—")
                            else:
                                st.metric("Total Amount", "—")

                        st.dataframe(df, use_container_width=True)

                        # Export row
                        st.markdown("#### 📥 Export")
                        e1, e2, _ = st.columns([2, 2, 6])

                        csv_bytes = export_df_to_csv_bytes(df)
                        with e1:
                            st.download_button(
                                "⬇️ Download CSV",
                                data=csv_bytes,
                                file_name="customer_statements.csv",
                                mime="text/csv",
                                use_container_width=True
                            )

                        # # PDF export (if reportlab available)
                        # with e2:
                        #     if REPORTLAB_AVAILABLE:
                        #         pdf_bytes = export_df_to_pdf_bytes(df, title="Customer Statements")
                        #         st.download_button(
                        #             "⬇️ Download PDF",
                        #             data=pdf_bytes,
                        #             file_name="customer_statements.pdf",
                        #             mime="application/pdf",
                        #             use_container_width=True
                        #         )
                        #     else:
                        #         st.warning(
                        #             "PDF export requires `reportlab`. Install with: `pip install reportlab`",
                        #             icon="⚠️"
                        #         )

                else:
                    st.info("No records found.")
            except oracledb.Error as err:
                st.error(f"Database error: {err}")
            except Exception as e:
                st.error(f"Unexpected error: {e}")
            finally:
                try:
                    if cursor: cursor.close()
                except Exception:
                    pass
                try:
                    if conn: conn.close()
                except Exception:
                    pass


# Pre-search / No results section
if not submitted or df is None or df.empty:
    st.divider()
    render_welcome()
