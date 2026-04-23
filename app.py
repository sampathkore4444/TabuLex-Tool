import streamlit as st
import pandas as pd
import tabula
from pathlib import Path
import os
import tempfile
import zipfile


# The core function from your notebook, slightly adapted for Streamlit context
def extract_tables_tabula_streamlit(
    pdf_path, output_dir="streamlit_tables", single_sql_file="all_insert_statements.sql"
):
    """
    Extract tables from PDF using tabula-py and generate CSV, Excel, and optionally a single SQL insert file.
    """
    # Ensure the output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # List to hold all SQL statements for a single file
    all_sql_statements = []
    extracted_files = []  # To keep track of all generated files for potential zipping

    try:
        # Extract all tables from PDF
        tables = tabula.read_pdf(pdf_path, pages="all", multiple_tables=True)
    except Exception as e:
        st.error(f"Error extracting tables from PDF: {e}")
        return [], []

    if not tables:
        st.warning("No tables found in the PDF.")
        return [], []

    st.write(f"Found {len(tables)} tables in the PDF.")

    # Store each table and generate SQL insert statements
    for i, table in enumerate(tables):
        if not table.empty:
            st.subheader(f"Table {i+1}")
            st.dataframe(table.head())

            # Save as CSV
            csv_path = output_path / f"table_{i+1}.csv"
            table.to_csv(csv_path, index=False)
            extracted_files.append(csv_path)
            st.success(f"Saved table {i+1} as CSV: {csv_path.name}")

            # Save as Excel
            excel_path = output_path / f"table_{i+1}.xlsx"
            table.to_excel(excel_path, index=False)
            extracted_files.append(excel_path)
            st.success(f"Saved table {i+1} as Excel: {excel_path.name}")

            # Generate SQL Insert Statements
            table_name = f"table_{i+1}"  # Using generic table names, adjust if specific names are needed

            # Sanitize column names for SQL: replace spaces with underscores, remove parentheses, newlines
            columns = ", ".join(
                [
                    f'"{(col.replace(" ", "_").replace("(", "").replace(")", "").replace("\r\n", "_").replace("\n", "_"))}"'
                    for col in table.columns
                ]
            )

            # Add a comment for the table
            all_sql_statements.append(f"-- Insert statements for {table_name}")

            for index, row in table.iterrows():
                values = []
                for val in row:
                    if pd.isna(val):
                        values.append("NULL")
                    elif isinstance(val, str):
                        # Escape single quotes within the string and handle newlines for SQL
                        clean_val = (
                            val.replace("'", "''")
                            .replace("\r\n", "\\n")
                            .replace("\n", "\\n")
                        )
                        values.append(f"'{clean_val}'")
                    else:
                        values.append(str(val))
                values_str = ", ".join(values)
                all_sql_statements.append(
                    f"INSERT INTO {table_name} ({columns}) VALUES ({values_str});"
                )
            all_sql_statements.append(
                "\n"
            )  # Add a newline for readability between tables

            st.write("-" * 50)

    # Write all collected SQL statements to a single file
    if all_sql_statements:
        single_sql_path = output_path / single_sql_file
        with open(single_sql_path, "w", encoding="utf-8") as f:
            f.write("\n".join(all_sql_statements))
        extracted_files.append(single_sql_path)
        st.success(f"All SQL insert statements saved to {single_sql_path.name}")

    return tables, extracted_files


st.title("PDF Table Extractor")
st.markdown(
    "Upload a PDF file to extract tables and generate CSV, Excel, and SQL insert statements."
)

uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

if uploaded_file is not None:
    with tempfile.TemporaryDirectory() as tmpdir:
        # Save the uploaded file temporarily
        temp_pdf_path = Path(tmpdir) / uploaded_file.name
        with open(temp_pdf_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        st.info(f"Processing PDF: {uploaded_file.name}...")

        # Define output directory within the temporary directory
        output_dir = Path(tmpdir) / "extracted_tables"
        output_dir.mkdir(exist_ok=True)

        extracted_tables, generated_files = extract_tables_tabula_streamlit(
            str(temp_pdf_path), output_dir=str(output_dir)
        )

        if generated_files:
            st.subheader("Download Extracted Files")

            # Create a zip file of all generated files
            zip_file_path = Path(tmpdir) / "extracted_data.zip"
            with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for file_path in generated_files:
                    zipf.write(
                        file_path, arcname=file_path.name
                    )  # Add file with just its name

            with open(zip_file_path, "rb") as f:
                st.download_button(
                    label="Download All Extracted Files (ZIP)",
                    data=f.read(),
                    file_name="extracted_data.zip",
                    mime="application/zip",
                )

            # Also offer individual downloads for SQL if it exists
            sql_file = output_dir / "all_insert_statements.sql"
            if sql_file.exists():
                with open(sql_file, "rb") as f:
                    st.download_button(
                        label="Download SQL Insert Statements",
                        data=f.read(),
                        file_name=sql_file.name,
                        mime="text/plain",
                    )

        if extracted_tables:
            st.success("Table extraction complete!")
        else:
            st.warning("No tables could be extracted or processed.")
