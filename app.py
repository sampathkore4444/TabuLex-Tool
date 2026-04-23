import streamlit as st
import pandas as pd
import pdfplumber
from pathlib import Path
import tempfile
import zipfile
import re


def extract_tables_pdfplumber_streamlit(
    pdf_path, output_dir="streamlit_tables", single_sql_file="all_insert_statements.sql"
):
    """
    Extract tables from PDF using pdfplumber and generate CSV, Excel, and SQL insert files.
    No Java required!
    """
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    all_sql_statements = []
    extracted_files = []
    all_tables = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                # Try different table extraction settings
                # First try: default settings
                tables = page.extract_tables()

                # If no tables found, try with table settings
                if not tables or len(tables) == 0:
                    # Try with custom table detection
                    tables = page.extract_tables(
                        {"vertical_strategy": "lines", "horizontal_strategy": "lines"}
                    )

                for table_num, table in enumerate(tables, 1):
                    if table and len(table) > 1:
                        # Clean and convert to DataFrame
                        # Find first non-empty row as header
                        header_row = None
                        data_rows = []

                        for row_idx, row in enumerate(table):
                            # Check if row has any non-empty/None values
                            if any(
                                cell is not None and str(cell).strip() for cell in row
                            ):
                                if header_row is None:
                                    # Use this as header
                                    header_row = [
                                        str(cell).strip() if cell else f"Column_{i+1}"
                                        for i, cell in enumerate(row)
                                    ]
                                else:
                                    # This is a data row
                                    clean_row = [
                                        str(cell).strip() if cell else ""
                                        for cell in row
                                    ]
                                    data_rows.append(clean_row)

                        if header_row and data_rows:
                            # Create DataFrame
                            df = pd.DataFrame(data_rows, columns=header_row)

                            # Remove completely empty rows and columns
                            df = df.replace(r"^\s*$", pd.NA, regex=True)
                            df = df.dropna(how="all").dropna(axis=1, how="all")

                            if not df.empty:
                                all_tables.append(df)

                                # Display table
                                st.subheader(
                                    f"Table {len(all_tables)} (Page {page_num})"
                                )
                                st.dataframe(df.head())

                                # Save as CSV
                                csv_path = output_path / f"table_{len(all_tables)}.csv"
                                df.to_csv(csv_path, index=False)
                                extracted_files.append(csv_path)
                                st.success(f"Saved as CSV: {csv_path.name}")

                                # Save as Excel
                                excel_path = (
                                    output_path / f"table_{len(all_tables)}.xlsx"
                                )
                                df.to_excel(excel_path, index=False)
                                extracted_files.append(excel_path)
                                st.success(f"Saved as Excel: {excel_path.name}")

                                # Generate SQL
                                table_name = f"table_{len(all_tables)}"
                                # Sanitize column names
                                columns = ", ".join(
                                    [
                                        f'"{re.sub(r"[^\w]", "_", str(col))}"'
                                        for col in df.columns
                                    ]
                                )

                                all_sql_statements.append(
                                    f"-- Insert statements for {table_name}"
                                )

                                for _, row in df.iterrows():
                                    values = []
                                    for val in row:
                                        if pd.isna(val) or val == "":
                                            values.append("NULL")
                                        elif isinstance(val, str):
                                            clean_val = (
                                                val.replace("'", "''")
                                                .replace("\n", "\\n")
                                                .replace("\r", "")
                                            )
                                            values.append(f"'{clean_val}'")
                                        else:
                                            values.append(str(val))

                                    values_str = ", ".join(values)
                                    all_sql_statements.append(
                                        f"INSERT INTO {table_name} ({columns}) VALUES ({values_str});"
                                    )

                                all_sql_statements.append("\n")
                                st.write("-" * 50)

        if all_tables and all_sql_statements:
            single_sql_path = output_path / single_sql_file
            with open(single_sql_path, "w", encoding="utf-8") as f:
                f.write("\n".join(all_sql_statements))
            extracted_files.append(single_sql_path)
            st.success(f"SQL insert statements saved to {single_sql_path.name}")

        return all_tables, extracted_files

    except Exception as e:
        st.error(f"Error extracting tables from PDF: {e}")
        st.info(
            "💡 Tip: Make sure your PDF has clearly formatted tables with borders or consistent spacing."
        )
        return [], []


st.set_page_config(page_title="PDF Table Extractor", layout="wide")
st.title("📊 PDF Table Extractor")
st.markdown(
    "Upload a PDF file to extract tables and generate CSV, Excel, and SQL insert statements."
)
st.info(
    "⚠️ **Note:** This version uses pdfplumber and does NOT require Java. It works on Streamlit Cloud without any additional setup!"
)

uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

if uploaded_file is not None:
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_pdf_path = Path(tmpdir) / uploaded_file.name
        with open(temp_pdf_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        st.info(f"📄 Processing PDF: {uploaded_file.name}...")

        output_dir = Path(tmpdir) / "extracted_tables"
        output_dir.mkdir(exist_ok=True)

        with st.spinner("Extracting tables from PDF..."):
            extracted_tables, generated_files = extract_tables_pdfplumber_streamlit(
                str(temp_pdf_path), output_dir=str(output_dir)
            )

        if generated_files:
            st.subheader("📥 Download Extracted Files")

            # Create ZIP file
            zip_file_path = Path(tmpdir) / "extracted_data.zip"
            with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for file_path in generated_files:
                    zipf.write(file_path, arcname=file_path.name)

            # Download buttons in columns
            col1, col2 = st.columns(2)

            with col1:
                with open(zip_file_path, "rb") as f:
                    st.download_button(
                        label="📦 Download All Files (ZIP)",
                        data=f.read(),
                        file_name="extracted_data.zip",
                        mime="application/zip",
                        use_container_width=True,
                    )

            # Individual file downloads
            with st.expander("📁 Download Individual Files"):
                for file_path in generated_files:
                    with open(file_path, "rb") as f:
                        st.download_button(
                            label=f"📄 {file_path.name}",
                            data=f.read(),
                            file_name=file_path.name,
                            mime="application/octet-stream",
                            key=str(file_path),
                        )

        if extracted_tables:
            st.success(
                f"✅ Successfully extracted {len(extracted_tables)} tables from your PDF!"
            )
        else:
            st.warning("⚠️ No tables could be extracted.")
            st.info(
                """
            **Troubleshooting tips:**
            - Make sure your PDF contains tables with clear borders or consistent formatting
            - Try a different PDF file
            - If your PDF has scanned images, you'll need OCR (Optical Character Recognition)
            """
            )
