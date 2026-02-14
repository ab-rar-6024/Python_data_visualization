"""
Combined Dashboard - Python Version
Converted from R Shiny to Streamlit
Features: Data upload/edit, visualizations
"""

import warnings
warnings.filterwarnings('ignore', category=FutureWarning)

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime, timedelta
from io import BytesIO
import os

# ══════════════════════════════════════════════════════════════════════════════
# 1. CONFIGURATION & SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Combined Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'df' not in st.session_state:
    st.session_state.df = None
if 'uploaded_files' not in st.session_state:
    st.session_state.uploaded_files = {}  # Dictionary to store multiple dataframes
if 'active_file' not in st.session_state:
    st.session_state.active_file = None  # Currently selected file

# ══════════════════════════════════════════════════════════════════════════════
# 2. UTILITY FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def convert_df_to_excel(df):
    """Convert dataframe to Excel bytes"""
    try:
        output = BytesIO()
        # Create a copy to avoid modifying original
        df_export = df.copy()
        
        # Ensure all columns have valid names
        df_export.columns = [str(col) if col else f'Column_{i}' for i, col in enumerate(df_export.columns)]
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Sheet1')
        
        output.seek(0)
        return output.getvalue()
    except Exception as e:
        raise Exception(f"Failed to convert DataFrame to Excel: {str(e)}")

def make_arrow_compatible(df):
    """Ensure DataFrame is compatible with Arrow serialization"""
    df_copy = df.copy()
    
    for col in df_copy.columns:
        # Ensure consistent dtype per column
        if df_copy[col].dtype == 'object':
            # Check if column has mixed types or empty strings that should be NaN
            try:
                # Try converting to numeric
                numeric_series = pd.to_numeric(df_copy[col], errors='coerce')
                # If we get some valid numbers, this might be a numeric column
                if numeric_series.notna().any():
                    # Replace empty strings with NaN
                    df_copy[col] = df_copy[col].replace('', pd.NA)
                    # Try converting again
                    converted = pd.to_numeric(df_copy[col], errors='ignore')
                    df_copy[col] = converted
                else:
                    # Keep as string but ensure consistent dtype
                    df_copy[col] = df_copy[col].astype(str)
            except:
                # Keep as string type
                df_copy[col] = df_copy[col].astype(str)
        
        # Handle any remaining dtype issues
        if df_copy[col].dtype == 'object':
            # Ensure all values are strings to avoid mixed types
            df_copy[col] = df_copy[col].fillna('').astype(str)
    
    return df_copy

# ══════════════════════════════════════════════════════════════════════════════
# 3. PAGE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def upload_files_page():
    """Upload Files Page"""
    st.header("📤 Upload Files")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Upload Files")
        
        # Multiple file upload
        uploaded_files = st.file_uploader("Upload CSV/XLSX (Multiple files supported)", 
                                         type=['csv', 'xlsx'], 
                                         accept_multiple_files=True,
                                         key="file_uploader")
        
        if uploaded_files:
            for uploaded_file in uploaded_files:
                if uploaded_file.name not in st.session_state.uploaded_files:
                    try:
                        if uploaded_file.name.endswith('.csv'):
                            df_new = pd.read_csv(uploaded_file, keep_default_na=False)
                        else:
                            # Read Excel with proper header handling
                            df_temp = pd.read_excel(uploaded_file, header=None, keep_default_na=False)
                            
                            # Find the actual header row (first non-empty row)
                            header_row = 0
                            for idx, row in df_temp.iterrows():
                                if row.notna().any() and any(str(val).strip() for val in row if pd.notna(val)):
                                    header_row = idx
                                    break
                            
                            # Re-read with correct header and treat everything as string initially
                            df_new = pd.read_excel(uploaded_file, header=header_row, keep_default_na=False, dtype=str)
                            
                            # Clean column names - remove "Unnamed" columns
                            new_columns = []
                            for col in df_new.columns:
                                if isinstance(col, str) and col.startswith('Unnamed'):
                                    new_columns.append('')
                                else:
                                    new_columns.append(str(col).strip())
                            df_new.columns = new_columns
                            
                            # Convert columns to appropriate types where possible
                            for col in df_new.columns:
                                if col:  # Skip empty column names
                                    try:
                                        # Try to convert to numeric
                                        numeric_col = pd.to_numeric(df_new[col], errors='coerce')
                                        # If more than 50% of non-empty values are numeric, keep as numeric
                                        non_empty = df_new[col].replace('', pd.NA)
                                        if numeric_col.notna().sum() > len(non_empty.dropna()) * 0.5:
                                            # Replace empty strings with NaN for numeric columns
                                            df_new[col] = df_new[col].replace('', pd.NA)
                                            df_new[col] = pd.to_numeric(df_new[col], errors='coerce')
                                    except:
                                        pass  # Keep as string if conversion fails
                        
                        # Store the dataframe with filename as key
                        st.session_state.uploaded_files[uploaded_file.name] = df_new
                        
                        # Set as active file if it's the first one
                        if st.session_state.active_file is None:
                            st.session_state.active_file = uploaded_file.name
                            st.session_state.df = df_new
                        
                        st.success(f"✅ Uploaded: {uploaded_file.name}")
                    except Exception as e:
                        st.error(f"Error loading {uploaded_file.name}: {str(e)}")
        
        st.divider()
        
        # Display uploaded files with delete option
        if st.session_state.uploaded_files:
            st.subheader("📂 Uploaded Files")
            
            for filename in list(st.session_state.uploaded_files.keys()):
                col_a, col_b, col_c = st.columns([3, 1, 1])
                
                with col_a:
                    is_active = filename == st.session_state.active_file
                    label = f"{'✓ ' if is_active else ''}{filename}"
                    if st.button(label, key=f"select_{filename}", width='stretch', 
                               type="primary" if is_active else "secondary"):
                        st.session_state.active_file = filename
                        st.session_state.df = st.session_state.uploaded_files[filename]
                        st.rerun()
                
                with col_b:
                    df_info = st.session_state.uploaded_files[filename]
                    st.caption(f"{df_info.shape[0]}×{df_info.shape[1]}")
                
                with col_c:
                    if st.button("🗑️", key=f"delete_{filename}", help=f"Delete {filename}"):
                        del st.session_state.uploaded_files[filename]
                        
                        # Update active file if deleted
                        if st.session_state.active_file == filename:
                            if st.session_state.uploaded_files:
                                # Set to first available file
                                st.session_state.active_file = list(st.session_state.uploaded_files.keys())[0]
                                st.session_state.df = st.session_state.uploaded_files[st.session_state.active_file]
                            else:
                                # No files left
                                st.session_state.active_file = None
                                st.session_state.df = None
                        
                        st.rerun()
        else:
            st.info("👆 Upload files to get started")
        
        st.divider()
        
        # Export data
        if st.session_state.df is not None and not st.session_state.df.empty:
            st.subheader("💾 Export")
            
            # Generate fresh Excel data on each render to avoid session issues
            try:
                excel_data = convert_df_to_excel(st.session_state.df)
                export_name = st.session_state.active_file if st.session_state.active_file else "data.xlsx"
                
                st.download_button(
                    label=f"⬇️ Export {export_name}",
                    data=excel_data,
                    file_name=export_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width='stretch',
                    key="download_data_excel"
                )
            except Exception as e:
                st.error(f"Error generating Excel file: {str(e)}")
    
    with col2:
        st.subheader("Data Table")
        
        if st.session_state.df is not None:
            # Display current file info
            col_a, col_b = st.columns([1, 1])
            with col_a:
                if st.session_state.active_file:
                    st.info(f"📄 Viewing: **{st.session_state.active_file}**")
                edit_mode = st.checkbox("✏️ Enable Editing", value=True, key="edit_upload")
            with col_b:
                st.caption(f"📋 {st.session_state.df.shape[0]} rows × {st.session_state.df.shape[1]} columns")
            
            # Show all column names in an expander
            with st.expander("📝 View All Column Names", expanded=False):
                cols_per_row = 2
                cols_list = list(st.session_state.df.columns)
                for i in range(0, len(cols_list), cols_per_row):
                    cols_display = st.columns(cols_per_row)
                    for j, col_widget in enumerate(cols_display):
                        if i + j < len(cols_list):
                            col_widget.text(f"{i+j+1}. {cols_list[i+j]}")
            
            # Display table
            if edit_mode:
                # Make DataFrame Arrow-compatible before displaying
                display_df = make_arrow_compatible(st.session_state.df)
                edited_df = st.data_editor(
                    display_df,
                    width='stretch',
                    num_rows="dynamic",
                    height=500,
                    key="data_editor_upload"
                )
                # Update the stored dataframe
                st.session_state.df = edited_df
                if st.session_state.active_file:
                    st.session_state.uploaded_files[st.session_state.active_file] = edited_df
            else:
                display_df = make_arrow_compatible(st.session_state.df)
                st.dataframe(
                    display_df,
                    width='stretch',
                    height=500
                )
        else:
            st.info("👆 Upload a file to get started")

def create_dataset_page():
    """Create New Dataset Page"""
    st.header("➕ Create New Dataset")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Dataset Configuration")
        
        # Dataset name
        dataset_name = st.text_input("Dataset Name", "New_Dataset.xlsx", 
                                     help="Name for your new dataset")
        
        # Number of rows
        rows = st.number_input("Number of Rows", min_value=1, max_value=10000, value=10, step=1,
                              help="Initial number of rows (you can add more later)")
        
        # Column configuration
        st.subheader("Column Configuration")
        
        # Option 1: Simple comma-separated
        col_method = st.radio("Column Entry Method", 
                             ["Simple (comma-separated)", "Advanced (one per line)"],
                             help="Choose how you want to enter column names")
        
        if col_method == "Simple (comma-separated)":
            cols_input = st.text_input("Column Names (comma-separated)", "Column1,Column2,Column3",
                                      help="Enter column names separated by commas")
            col_names = [c.strip() for c in cols_input.split(',') if c.strip()]
        else:
            cols_input = st.text_area("Column Names (one per line)", 
                                     "Column1\nColumn2\nColumn3",
                                     height=200,
                                     help="Enter each column name on a new line")
            col_names = [c.strip() for c in cols_input.split('\n') if c.strip()]
        
        # Preview
        if col_names:
            st.info(f"📊 Preview: {len(col_names)} columns, {rows} rows")
            with st.expander("Column Names Preview", expanded=False):
                for idx, col in enumerate(col_names, 1):
                    st.text(f"{idx}. {col}")
        
        st.divider()
        
        # Create button
        if st.button("➕ Create Dataset", width='stretch', type="primary"):
            if col_names:
                # Create DataFrame with empty strings and explicit object dtype
                data = {col: pd.Series([''] * int(rows), dtype='object') for col in col_names}
                new_df = pd.DataFrame(data)
                
                # Ensure unique filename
                base_name = dataset_name if dataset_name else "New_Dataset.xlsx"
                final_name = base_name
                counter = 1
                while final_name in st.session_state.uploaded_files:
                    name_parts = base_name.rsplit('.', 1)
                    if len(name_parts) == 2:
                        final_name = f"{name_parts[0]}_{counter}.{name_parts[1]}"
                    else:
                        final_name = f"{base_name}_{counter}"
                    counter += 1
                
                st.session_state.uploaded_files[final_name] = new_df
                st.session_state.active_file = final_name
                st.session_state.df = new_df
                
                st.success(f"✅ Created dataset '{final_name}' with {int(rows)} rows and {len(col_names)} columns")
                st.balloons()
                st.info("💡 You can now edit your dataset in the table on the right, or go to 'Upload Files' to view/manage all datasets")
            else:
                st.error("⚠️ Please enter at least one column name")
        
        st.divider()
        
        # Quick templates
        st.subheader("📋 Quick Templates")
        
        template = st.selectbox("Choose a template", 
                               ["Custom", "Student Records", "Sales Data", "Inventory", "Employee Data"])
        
        if template != "Custom":
            if st.button("Load Template", width='stretch'):
                templates = {
                    "Student Records": {
                        "name": "Student_Records.xlsx",
                        "columns": ["Student ID", "Name", "Age", "Grade", "Subject", "Score", "Attendance %"],
                        "rows": 20
                    },
                    "Sales Data": {
                        "name": "Sales_Data.xlsx",
                        "columns": ["Date", "Product", "Category", "Quantity", "Unit Price", "Total", "Region"],
                        "rows": 50
                    },
                    "Inventory": {
                        "name": "Inventory.xlsx",
                        "columns": ["Item ID", "Item Name", "Category", "Quantity", "Unit", "Price", "Supplier", "Last Updated"],
                        "rows": 30
                    },
                    "Employee Data": {
                        "name": "Employee_Data.xlsx",
                        "columns": ["Employee ID", "Name", "Department", "Position", "Hire Date", "Salary", "Email"],
                        "rows": 25
                    }
                }
                
                template_config = templates[template]
                data = {col: pd.Series([''] * template_config["rows"], dtype='object') 
                       for col in template_config["columns"]}
                new_df = pd.DataFrame(data)
                
                # Ensure unique filename
                base_name = template_config["name"]
                final_name = base_name
                counter = 1
                while final_name in st.session_state.uploaded_files:
                    name_parts = base_name.rsplit('.', 1)
                    final_name = f"{name_parts[0]}_{counter}.{name_parts[1]}"
                    counter += 1
                
                st.session_state.uploaded_files[final_name] = new_df
                st.session_state.active_file = final_name
                st.session_state.df = new_df
                
                st.success(f"✅ Loaded template '{final_name}'")
                st.rerun()
    
    with col2:
        st.subheader("Data Table")
        
        if st.session_state.df is not None:
            # Display current file info
            col_a, col_b = st.columns([1, 1])
            with col_a:
                if st.session_state.active_file:
                    st.info(f"📄 Editing: **{st.session_state.active_file}**")
                edit_mode = st.checkbox("✏️ Enable Editing", value=True, key="edit_create")
            with col_b:
                st.caption(f"📋 {st.session_state.df.shape[0]} rows × {st.session_state.df.shape[1]} columns")
            
            # Show all column names in an expander
            with st.expander("📝 View All Column Names", expanded=False):
                cols_per_row = 2
                cols_list = list(st.session_state.df.columns)
                for i in range(0, len(cols_list), cols_per_row):
                    cols_display = st.columns(cols_per_row)
                    for j, col_widget in enumerate(cols_display):
                        if i + j < len(cols_list):
                            col_widget.text(f"{i+j+1}. {cols_list[i+j]}")
            
            # Display table
            if edit_mode:
                # Make DataFrame Arrow-compatible before displaying
                display_df = make_arrow_compatible(st.session_state.df)
                edited_df = st.data_editor(
                    display_df,
                    width='stretch',
                    num_rows="dynamic",
                    height=500,
                    key="data_editor_create"
                )
                # Update the stored dataframe
                st.session_state.df = edited_df
                if st.session_state.active_file:
                    st.session_state.uploaded_files[st.session_state.active_file] = edited_df
            else:
                display_df = make_arrow_compatible(st.session_state.df)
                st.dataframe(
                    display_df,
                    width='stretch',
                    height=500
                )
            
            # Export option
            st.divider()
            try:
                excel_data = convert_df_to_excel(st.session_state.df)
                export_name = st.session_state.active_file if st.session_state.active_file else "dataset.xlsx"
                
                st.download_button(
                    label=f"⬇️ Download {export_name}",
                    data=excel_data,
                    file_name=export_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width='stretch',
                    key="download_created_dataset"
                )
            except Exception as e:
                st.error(f"Error generating Excel file: {str(e)}")
        else:
            st.info("👆 Configure and create a dataset to get started")
            st.markdown("""
            ### How to use:
            1. Enter a name for your dataset
            2. Choose number of rows
            3. Enter column names (comma-separated or one per line)
            4. Click 'Create Dataset'
            5. Start editing in the table!
            
            Or use a **Quick Template** to get started faster.
            """)
    """Data Upload / Load Tab"""
    st.header("📤 Upload / Load Data")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Upload / Create")
        
        # Multiple file upload
        uploaded_files = st.file_uploader("Upload CSV/XLSX (Multiple files supported)", 
                                         type=['csv', 'xlsx'], 
                                         accept_multiple_files=True)
        
        if uploaded_files:
            for uploaded_file in uploaded_files:
                if uploaded_file.name not in st.session_state.uploaded_files:
                    try:
                        if uploaded_file.name.endswith('.csv'):
                            df_new = pd.read_csv(uploaded_file, keep_default_na=False)
                        else:
                            # Read Excel with proper header handling
                            df_temp = pd.read_excel(uploaded_file, header=None, keep_default_na=False)
                            
                            # Find the actual header row (first non-empty row)
                            header_row = 0
                            for idx, row in df_temp.iterrows():
                                if row.notna().any() and any(str(val).strip() for val in row if pd.notna(val)):
                                    header_row = idx
                                    break
                            
                            # Re-read with correct header and treat everything as string initially
                            df_new = pd.read_excel(uploaded_file, header=header_row, keep_default_na=False, dtype=str)
                            
                            # Clean column names - remove "Unnamed" columns
                            new_columns = []
                            for col in df_new.columns:
                                if isinstance(col, str) and col.startswith('Unnamed'):
                                    new_columns.append('')
                                else:
                                    new_columns.append(str(col).strip())
                            df_new.columns = new_columns
                            
                            # Convert columns to appropriate types where possible
                            for col in df_new.columns:
                                if col:  # Skip empty column names
                                    try:
                                        # Try to convert to numeric
                                        numeric_col = pd.to_numeric(df_new[col], errors='coerce')
                                        # If more than 50% of non-empty values are numeric, keep as numeric
                                        non_empty = df_new[col].replace('', pd.NA)
                                        if numeric_col.notna().sum() > len(non_empty.dropna()) * 0.5:
                                            # Replace empty strings with NaN for numeric columns
                                            df_new[col] = df_new[col].replace('', pd.NA)
                                            df_new[col] = pd.to_numeric(df_new[col], errors='coerce')
                                    except:
                                        pass  # Keep as string if conversion fails
                        
                        # Store the dataframe with filename as key
                        st.session_state.uploaded_files[uploaded_file.name] = df_new
                        
                        # Set as active file if it's the first one
                        if st.session_state.active_file is None:
                            st.session_state.active_file = uploaded_file.name
                            st.session_state.df = df_new
                        
                        st.success(f"✅ Uploaded: {uploaded_file.name}")
                    except Exception as e:
                        st.error(f"Error loading {uploaded_file.name}: {str(e)}")
        
        st.divider()
        
        # Display uploaded files with delete option
        if st.session_state.uploaded_files:
            st.subheader("📂 Uploaded Files")
            
            for filename in list(st.session_state.uploaded_files.keys()):
                col_a, col_b, col_c = st.columns([3, 1, 1])
                
                with col_a:
                    is_active = filename == st.session_state.active_file
                    label = f"{'✓ ' if is_active else ''}{filename}"
                    if st.button(label, key=f"select_{filename}", width='stretch', 
                               type="primary" if is_active else "secondary"):
                        st.session_state.active_file = filename
                        st.session_state.df = st.session_state.uploaded_files[filename]
                        st.rerun()
                
                with col_b:
                    df_info = st.session_state.uploaded_files[filename]
                    st.caption(f"{df_info.shape[0]}×{df_info.shape[1]}")
                
                with col_c:
                    if st.button("🗑️", key=f"delete_{filename}", help=f"Delete {filename}"):
                        del st.session_state.uploaded_files[filename]
                        
                        # Update active file if deleted
                        if st.session_state.active_file == filename:
                            if st.session_state.uploaded_files:
                                # Set to first available file
                                st.session_state.active_file = list(st.session_state.uploaded_files.keys())[0]
                                st.session_state.df = st.session_state.uploaded_files[st.session_state.active_file]
                            else:
                                # No files left
                                st.session_state.active_file = None
                                st.session_state.df = None
                        
                        st.rerun()
            
            st.divider()
        
        # Create new dataset
        st.subheader("Create New Dataset")
        rows = st.number_input("Number of rows", min_value=1, value=5, step=1)
        cols_input = st.text_input("Column names (comma-separated)", "A,B,C")
        dataset_name = st.text_input("Dataset name", "New_Dataset.xlsx")
        
        if st.button("➕ Create Dataset", width='stretch'):
            col_names = [c.strip() for c in cols_input.split(',') if c.strip()]
            if col_names:
                # Create DataFrame with empty strings and explicit object dtype
                data = {col: pd.Series([''] * int(rows), dtype='object') for col in col_names}
                new_df = pd.DataFrame(data)
                
                # Ensure unique filename
                base_name = dataset_name if dataset_name else "New_Dataset.xlsx"
                final_name = base_name
                counter = 1
                while final_name in st.session_state.uploaded_files:
                    name_parts = base_name.rsplit('.', 1)
                    if len(name_parts) == 2:
                        final_name = f"{name_parts[0]}_{counter}.{name_parts[1]}"
                    else:
                        final_name = f"{base_name}_{counter}"
                    counter += 1
                
                st.session_state.uploaded_files[final_name] = new_df
                st.session_state.active_file = final_name
                st.session_state.df = new_df
                
                st.success(f"Created dataset '{final_name}' with {int(rows)} rows and {len(col_names)} columns")
                st.rerun()
            else:
                st.error("Please enter at least one column name")
        
        st.divider()
        
        # Export data
        if st.session_state.df is not None and not st.session_state.df.empty:
            st.subheader("💾 Export")
            
            # Generate fresh Excel data on each render to avoid session issues
            try:
                excel_data = convert_df_to_excel(st.session_state.df)
                export_name = st.session_state.active_file if st.session_state.active_file else "data.xlsx"
                
                st.download_button(
                    label=f"⬇️ Export {export_name}",
                    data=excel_data,
                    file_name=export_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width='stretch',
                    key="download_data_excel"
                )
            except Exception as e:
                st.error(f"Error generating Excel file: {str(e)}")
    
    with col2:
        st.subheader("Data Table")
        
        if st.session_state.df is not None:
            # Display current file info
            col_a, col_b = st.columns([1, 1])
            with col_a:
                if st.session_state.active_file:
                    st.info(f"📄 Viewing: **{st.session_state.active_file}**")
                edit_mode = st.checkbox("✏️ Enable Editing", value=True)
            with col_b:
                st.caption(f"📋 {st.session_state.df.shape[0]} rows × {st.session_state.df.shape[1]} columns")
            
            # Show all column names in an expander
            with st.expander("📝 View All Column Names", expanded=False):
                cols_per_row = 2
                cols_list = list(st.session_state.df.columns)
                for i in range(0, len(cols_list), cols_per_row):
                    cols_display = st.columns(cols_per_row)
                    for j, col_widget in enumerate(cols_display):
                        if i + j < len(cols_list):
                            col_widget.text(f"{i+j+1}. {cols_list[i+j]}")
            
            # Display table
            if edit_mode:
                # Make DataFrame Arrow-compatible before displaying
                display_df = make_arrow_compatible(st.session_state.df)
                edited_df = st.data_editor(
                    display_df,
                    width='stretch',
                    num_rows="dynamic",
                    height=500
                )
                # Update the stored dataframe
                st.session_state.df = edited_df
                if st.session_state.active_file:
                    st.session_state.uploaded_files[st.session_state.active_file] = edited_df
            else:
                display_df = make_arrow_compatible(st.session_state.df)
                st.dataframe(
                    display_df,
                    width='stretch',
                    height=500
                )
        else:
            st.info("👆 Upload a file or create a new dataset to get started")

def visualize_page():
    """Visualization Tab"""
    st.header("📊 Visualize Data")
    
    if st.session_state.df is None or st.session_state.df.empty:
        st.warning("⚠️ No data available. Please upload or create data in the 'Upload / Load' tab.")
        return
    
    df = st.session_state.df.copy()
    
    # Data preprocessing
    # Identify numeric and categorical columns
    numeric_cols = df.select_dtypes(include=['int64', 'float64', 'int32', 'float32']).columns.tolist()
    categorical_cols = df.select_dtypes(include=['object', 'category', 'bool']).columns.tolist()
    all_cols = df.columns.tolist()
    
    # Try to convert string columns to numeric where possible
    for col in categorical_cols:
        try:
            converted = pd.to_numeric(df[col])
            df[col] = converted
        except (ValueError, TypeError):
            pass  # Keep as categorical if conversion fails
    
    # Re-identify after conversion
    numeric_cols = df.select_dtypes(include=['int64', 'float64', 'int32', 'float32']).columns.tolist()
    categorical_cols = df.select_dtypes(include=['object', 'category', 'bool']).columns.tolist()
    
    # Create tabs for different types of visualizations
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Charts", "📊 Statistical Analysis", "🔢 Data Summary", "📋 Custom Plot"])
    
    # ═══════════════════════════════════════════════════════════════════════
    # TAB 1: CHARTS
    # ═══════════════════════════════════════════════════════════════════════
    with tab1:
        st.subheader("Chart Builder")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            plot_type = st.selectbox(
                "Chart Type",
                ["Scatter Plot", "Line Chart", "Bar Chart", "Horizontal Bar", 
                 "Box Plot", "Violin Plot", "Histogram", "Density Plot",
                 "Pie Chart", "Donut Chart", "Area Chart", "Bubble Chart",
                 "Heatmap", "Correlation Matrix"]
            )
        
        with col2:
            if plot_type in ["Heatmap", "Correlation Matrix"]:
                x_col = None
            else:
                x_col = st.selectbox("X-axis", all_cols, key="x_axis_tab1")
        
        with col3:
            if plot_type in ["Histogram", "Density Plot", "Pie Chart", "Donut Chart"]:
                y_col = None
            elif plot_type in ["Heatmap", "Correlation Matrix"]:
                y_col = None
            else:
                available_y = all_cols if plot_type == "Scatter Plot" else numeric_cols + all_cols
                y_col = st.selectbox("Y-axis", available_y, key="y_axis_tab1")
        
        with col4:
            color_by = st.selectbox("Color By", ["None"] + categorical_cols, key="color_tab1")
            color_by = None if color_by == "None" else color_by
        
        # Additional options
        col5, col6 = st.columns(2)
        with col5:
            if plot_type == "Bubble Chart":
                size_col = st.selectbox("Size By", numeric_cols, key="size_bubble")
            color_choice = st.color_picker("Primary Color", "#2E86C1", key="color1")
        
        with col6:
            show_title = st.checkbox("Show Title", value=True, key="title_check1")
            if show_title:
                chart_title = st.text_input("Chart Title", f"{plot_type}", key="title_text1")
        
        st.divider()
        
        # Generate plot
        try:
            fig = None
            
            if plot_type == "Scatter Plot":
                fig = px.scatter(df, x=x_col, y=y_col, color=color_by,
                               color_discrete_sequence=[color_choice],
                               title=chart_title if show_title else None)
            
            elif plot_type == "Line Chart":
                fig = px.line(df, x=x_col, y=y_col, color=color_by,
                            color_discrete_sequence=[color_choice],
                            title=chart_title if show_title else None)
            
            elif plot_type == "Bar Chart":
                if y_col:
                    fig = px.bar(df, x=x_col, y=y_col, color=color_by,
                               color_discrete_sequence=[color_choice],
                               title=chart_title if show_title else None)
                else:
                    # Count plot
                    count_df = df[x_col].value_counts().reset_index()
                    count_df.columns = [x_col, 'Count']
                    fig = px.bar(count_df, x=x_col, y='Count',
                               color_discrete_sequence=[color_choice],
                               title=chart_title if show_title else None)
            
            elif plot_type == "Horizontal Bar":
                if y_col:
                    fig = px.bar(df, x=y_col, y=x_col, color=color_by,
                               orientation='h',
                               color_discrete_sequence=[color_choice],
                               title=chart_title if show_title else None)
                else:
                    count_df = df[x_col].value_counts().reset_index()
                    count_df.columns = [x_col, 'Count']
                    fig = px.bar(count_df, x='Count', y=x_col,
                               orientation='h',
                               color_discrete_sequence=[color_choice],
                               title=chart_title if show_title else None)
            
            elif plot_type == "Box Plot":
                fig = px.box(df, x=x_col, y=y_col, color=color_by,
                           color_discrete_sequence=[color_choice],
                           title=chart_title if show_title else None)
            
            elif plot_type == "Violin Plot":
                fig = px.violin(df, x=x_col, y=y_col, color=color_by,
                              color_discrete_sequence=[color_choice],
                              title=chart_title if show_title else None)
            
            elif plot_type == "Histogram":
                fig = px.histogram(df, x=x_col, color=color_by,
                                 color_discrete_sequence=[color_choice],
                                 title=chart_title if show_title else None)
            
            elif plot_type == "Density Plot":
                # Create density plot manually
                fig = go.Figure()
                if color_by and color_by in df.columns:
                    for category in df[color_by].unique():
                        subset = df[df[color_by] == category][x_col].dropna()
                        fig.add_trace(go.Violin(x=subset, name=str(category), 
                                               box_visible=False, meanline_visible=False))
                else:
                    subset = df[x_col].dropna()
                    fig.add_trace(go.Violin(x=subset, name=x_col,
                                           box_visible=False, meanline_visible=False,
                                           line_color=color_choice))
                fig.update_layout(title=chart_title if show_title else None)
            
            elif plot_type == "Pie Chart":
                pie_df = df[x_col].value_counts().reset_index()
                pie_df.columns = [x_col, 'Count']
                fig = px.pie(pie_df, names=x_col, values='Count',
                           title=chart_title if show_title else None)
            
            elif plot_type == "Donut Chart":
                pie_df = df[x_col].value_counts().reset_index()
                pie_df.columns = [x_col, 'Count']
                fig = px.pie(pie_df, names=x_col, values='Count',
                           hole=0.4,
                           title=chart_title if show_title else None)
            
            elif plot_type == "Area Chart":
                fig = px.area(df, x=x_col, y=y_col, color=color_by,
                            color_discrete_sequence=[color_choice],
                            title=chart_title if show_title else None)
            
            elif plot_type == "Bubble Chart":
                fig = px.scatter(df, x=x_col, y=y_col, size=size_col, color=color_by,
                               color_discrete_sequence=[color_choice],
                               title=chart_title if show_title else None)
            
            elif plot_type == "Heatmap":
                # Create heatmap from numeric columns
                numeric_df = df[numeric_cols]
                fig = px.imshow(numeric_df.T, 
                              labels=dict(x="Row", y="Column", color="Value"),
                              title=chart_title if show_title else None,
                              aspect="auto")
            
            elif plot_type == "Correlation Matrix":
                # Calculate correlation matrix
                if len(numeric_cols) > 1:
                    corr_matrix = df[numeric_cols].corr()
                    fig = px.imshow(corr_matrix,
                                  labels=dict(color="Correlation"),
                                  x=corr_matrix.columns,
                                  y=corr_matrix.columns,
                                  title=chart_title if show_title else None,
                                  color_continuous_scale='RdBu_r',
                                  zmin=-1, zmax=1)
                    # Add correlation values as text
                    fig.update_traces(text=corr_matrix.round(2).values,
                                    texttemplate='%{text}')
                else:
                    st.warning("⚠️ Need at least 2 numeric columns for correlation matrix")
            
            if fig:
                fig.update_layout(height=600, template="plotly_white")
                st.plotly_chart(fig, width='stretch')
        
        except Exception as e:
            st.error(f"Error creating plot: {str(e)}")
            st.info("💡 Make sure the selected columns are appropriate for the chosen plot type")
    
    # ═══════════════════════════════════════════════════════════════════════
    # TAB 2: STATISTICAL ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════
    with tab2:
        st.subheader("Statistical Analysis")
        
        if len(numeric_cols) == 0:
            st.warning("⚠️ No numeric columns found for statistical analysis")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 📊 Descriptive Statistics")
                selected_cols = st.multiselect("Select columns for analysis", 
                                              numeric_cols, 
                                              default=numeric_cols[:5] if len(numeric_cols) >= 5 else numeric_cols,
                                              key="stats_cols")
                
                if selected_cols:
                    stats_df = df[selected_cols].describe().T
                    stats_df['median'] = df[selected_cols].median()
                    stats_df['variance'] = df[selected_cols].var()
                    stats_df['skewness'] = df[selected_cols].skew()
                    stats_df['kurtosis'] = df[selected_cols].kurtosis()
                    
                    st.dataframe(stats_df.round(2), width='stretch')
                    
                    # Download stats - generate fresh on each render
                    try:
                        excel_stats = convert_df_to_excel(stats_df.round(2))
                        st.download_button(
                            label="⬇️ Download Statistics",
                            data=excel_stats,
                            file_name="statistics.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            width='stretch',
                            key="download_stats_excel"
                        )
                    except Exception as e:
                        st.error(f"Error generating statistics file: {str(e)}")
            
            with col2:
                st.markdown("#### 📈 Distribution Plot")
                dist_col = st.selectbox("Select column", numeric_cols, key="dist_col")
                
                if dist_col:
                    fig = go.Figure()
                    fig.add_trace(go.Histogram(x=df[dist_col], name='Histogram',
                                              marker_color=color_choice, opacity=0.7))
                    
                    # Add KDE curve
                    from scipy import stats as scipy_stats
                    try:
                        data = df[dist_col].dropna()
                        kde = scipy_stats.gaussian_kde(data)
                        x_range = np.linspace(data.min(), data.max(), 100)
                        kde_values = kde(x_range)
                        # Scale KDE to match histogram
                        kde_scaled = kde_values * len(data) * (data.max() - data.min()) / 30
                        
                        fig.add_trace(go.Scatter(x=x_range, y=kde_scaled,
                                               mode='lines', name='KDE',
                                               line=dict(color='red', width=2)))
                    except:
                        pass
                    
                    fig.update_layout(title=f"Distribution of {dist_col}",
                                    height=400, template="plotly_white",
                                    bargap=0.1)
                    st.plotly_chart(fig, width='stretch')
            
            # Correlation analysis
            if len(numeric_cols) > 1:
                st.markdown("#### 🔗 Correlation Analysis")
                
                col3, col4 = st.columns([2, 1])
                
                with col3:
                    corr_method = st.selectbox("Correlation method", 
                                              ["Pearson", "Spearman", "Kendall"],
                                              key="corr_method")
                    
                    corr_matrix = df[numeric_cols].corr(method=corr_method.lower())
                    
                    fig = px.imshow(corr_matrix,
                                  labels=dict(color="Correlation"),
                                  x=corr_matrix.columns,
                                  y=corr_matrix.columns,
                                  title=f"{corr_method} Correlation Matrix",
                                  color_continuous_scale='RdBu_r',
                                  zmin=-1, zmax=1)
                    fig.update_traces(text=corr_matrix.round(2).values,
                                    texttemplate='%{text}')
                    fig.update_layout(height=500)
                    st.plotly_chart(fig, width='stretch')
                
                with col4:
                    st.markdown("**Top Correlations**")
                    # Get top correlations
                    corr_pairs = []
                    for i in range(len(corr_matrix.columns)):
                        for j in range(i+1, len(corr_matrix.columns)):
                            corr_pairs.append({
                                'Variable 1': corr_matrix.columns[i],
                                'Variable 2': corr_matrix.columns[j],
                                'Correlation': corr_matrix.iloc[i, j]
                            })
                    
                    corr_df = pd.DataFrame(corr_pairs)
                    corr_df = corr_df.reindex(corr_df['Correlation'].abs().sort_values(ascending=False).index)
                    st.dataframe(corr_df.head(10).round(3), width='stretch', height=400)
    
    # ═══════════════════════════════════════════════════════════════════════
    # TAB 3: DATA SUMMARY
    # ═══════════════════════════════════════════════════════════════════════
    with tab3:
        st.subheader("Data Summary")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Rows", len(df))
        with col2:
            st.metric("Total Columns", len(df.columns))
        with col3:
            missing_count = df.isnull().sum().sum()
            st.metric("Missing Values", missing_count)
        
        st.divider()
        
        col4, col5 = st.columns(2)
        
        with col4:
            st.markdown("#### 📋 Column Information")
            col_info = pd.DataFrame({
                'Column': df.columns,
                'Data Type': [str(dtype) for dtype in df.dtypes.values],
                'Non-Null Count': df.count().values,
                'Null Count': df.isnull().sum().values,
                'Unique Values': [df[col].nunique() for col in df.columns]
            })
            st.dataframe(col_info, width='stretch', height=400)
        
        with col5:
            st.markdown("#### 🔍 Missing Data Pattern")
            missing_df = df.isnull().sum().reset_index()
            missing_df.columns = ['Column', 'Missing Count']
            missing_df = missing_df[missing_df['Missing Count'] > 0].sort_values('Missing Count', ascending=False)
            
            if len(missing_df) > 0:
                fig = px.bar(missing_df, x='Column', y='Missing Count',
                           title="Missing Values by Column",
                           color_discrete_sequence=[color_choice])
                fig.update_layout(height=400)
                st.plotly_chart(fig, width='stretch')
            else:
                st.success("✅ No missing values in dataset!")
        
        st.divider()
        
        # Value counts for categorical columns
        if categorical_cols:
            st.markdown("#### 📊 Categorical Variables Distribution")
            cat_col = st.selectbox("Select categorical column", categorical_cols, key="cat_summary")
            
            if cat_col:
                col6, col7 = st.columns([1, 1])
                
                with col6:
                    value_counts = df[cat_col].value_counts().reset_index()
                    value_counts.columns = [cat_col, 'Count']
                    st.dataframe(value_counts, width='stretch', height=300)
                
                with col7:
                    fig = px.pie(value_counts.head(10), names=cat_col, values='Count',
                               title=f"Distribution of {cat_col} (Top 10)")
                    fig.update_layout(height=300)
                    st.plotly_chart(fig, width='stretch')
    
    # ═══════════════════════════════════════════════════════════════════════
    # TAB 4: CUSTOM PLOT
    # ═══════════════════════════════════════════════════════════════════════
    with tab4:
        st.subheader("Custom Multi-Variable Plot")
        st.info("💡 Create complex visualizations with multiple variables")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            custom_plot_type = st.selectbox(
                "Plot Type",
                ["Scatter Matrix", "Parallel Coordinates", "3D Scatter", 
                 "Grouped Bar Chart", "Stacked Bar Chart", "Multiple Line Chart",
                 "Facet Grid", "Sunburst Chart", "Treemap"],
                key="custom_plot_type"
            )
        
        with col2:
            if custom_plot_type in ["Scatter Matrix", "Parallel Coordinates"]:
                plot_cols = st.multiselect("Select columns", numeric_cols, 
                                          default=numeric_cols[:4] if len(numeric_cols) >= 4 else numeric_cols,
                                          key="custom_cols")
            elif custom_plot_type == "3D Scatter":
                x_3d = st.selectbox("X-axis", numeric_cols, key="x_3d")
            elif custom_plot_type in ["Sunburst Chart", "Treemap"]:
                path_cols = st.multiselect("Hierarchy (path)", categorical_cols,
                                          default=categorical_cols[:2] if len(categorical_cols) >= 2 else categorical_cols,
                                          key="hierarchy_cols")
            else:
                x_custom = st.selectbox("X-axis", all_cols, key="x_custom")
        
        with col3:
            if custom_plot_type == "3D Scatter":
                y_3d = st.selectbox("Y-axis", numeric_cols, key="y_3d")
                z_3d = st.selectbox("Z-axis", numeric_cols, key="z_3d")
            elif custom_plot_type in ["Sunburst Chart", "Treemap"]:
                value_col = st.selectbox("Values", numeric_cols, key="value_col") if numeric_cols else None
            elif custom_plot_type not in ["Scatter Matrix", "Parallel Coordinates"]:
                y_custom = st.selectbox("Y-axis", numeric_cols, key="y_custom")
                if custom_plot_type in ["Grouped Bar Chart", "Stacked Bar Chart", "Multiple Line Chart", "Facet Grid"]:
                    group_col = st.selectbox("Group by", categorical_cols, key="group_custom")
        
        st.divider()
        
        try:
            fig = None
            
            if custom_plot_type == "Scatter Matrix":
                if plot_cols and len(plot_cols) >= 2:
                    fig = px.scatter_matrix(df, dimensions=plot_cols,
                                          title="Scatter Matrix")
                    fig.update_traces(diagonal_visible=False)
            
            elif custom_plot_type == "Parallel Coordinates":
                if plot_cols and len(plot_cols) >= 2:
                    fig = px.parallel_coordinates(df, dimensions=plot_cols,
                                                title="Parallel Coordinates Plot")
            
            elif custom_plot_type == "3D Scatter":
                if x_3d and y_3d and z_3d:
                    fig = px.scatter_3d(df, x=x_3d, y=y_3d, z=z_3d,
                                      color=color_by if color_by else None,
                                      title="3D Scatter Plot")
            
            elif custom_plot_type == "Grouped Bar Chart":
                if x_custom and y_custom and group_col:
                    fig = px.bar(df, x=x_custom, y=y_custom, color=group_col,
                               barmode='group',
                               title="Grouped Bar Chart")
            
            elif custom_plot_type == "Stacked Bar Chart":
                if x_custom and y_custom and group_col:
                    fig = px.bar(df, x=x_custom, y=y_custom, color=group_col,
                               barmode='stack',
                               title="Stacked Bar Chart")
            
            elif custom_plot_type == "Multiple Line Chart":
                if x_custom and y_custom and group_col:
                    fig = px.line(df, x=x_custom, y=y_custom, color=group_col,
                                title="Multiple Line Chart")
            
            elif custom_plot_type == "Facet Grid":
                if x_custom and y_custom and group_col:
                    # Check number of unique categories
                    n_categories = df[group_col].nunique()
                    
                    if n_categories > 20:
                        st.warning(f"⚠️ '{group_col}' has {n_categories} unique values. Showing top categories only.")
                        
                        # Let user select how many top categories to show
                        top_n = st.slider("Number of top categories to display", 
                                         min_value=5, max_value=20, value=10, step=1,
                                         key="facet_top_n")
                        
                        # Get top N categories by count
                        top_categories = df[group_col].value_counts().head(top_n).index.tolist()
                        df_filtered = df[df[group_col].isin(top_categories)].copy()
                        
                        st.info(f"💡 Displaying top {top_n} categories out of {n_categories} total")
                        
                        fig = px.scatter(df_filtered, x=x_custom, y=y_custom, facet_col=group_col,
                                       facet_col_wrap=5,  # Wrap to max 5 columns
                                       title=f"Facet Grid (Top {top_n} Categories)")
                    else:
                        # Determine appropriate wrap based on number of categories
                        wrap_cols = min(5, n_categories) if n_categories > 5 else None
                        
                        fig = px.scatter(df, x=x_custom, y=y_custom, facet_col=group_col,
                                       facet_col_wrap=wrap_cols,
                                       title="Facet Grid")
            
            elif custom_plot_type == "Sunburst Chart":
                if path_cols and len(path_cols) >= 1:
                    if value_col:
                        fig = px.sunburst(df, path=path_cols, values=value_col,
                                        title="Sunburst Chart")
                    else:
                        # Count-based sunburst
                        df_grouped = df.groupby(path_cols).size().reset_index(name='count')
                        fig = px.sunburst(df_grouped, path=path_cols, values='count',
                                        title="Sunburst Chart")
            
            elif custom_plot_type == "Treemap":
                if path_cols and len(path_cols) >= 1:
                    if value_col:
                        fig = px.treemap(df, path=path_cols, values=value_col,
                                       title="Treemap")
                    else:
                        # Count-based treemap
                        df_grouped = df.groupby(path_cols).size().reset_index(name='count')
                        fig = px.treemap(df_grouped, path=path_cols, values='count',
                                       title="Treemap")
            
            if fig:
                fig.update_layout(height=650, template="plotly_white")
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("👆 Configure the plot options above to create your visualization")
        
        except Exception as e:
            error_msg = str(e)
            st.error(f"Error creating plot: {error_msg}")
            
            # Provide specific guidance based on error
            if "facet_col_spacing" in error_msg.lower() or "horizontal spacing" in error_msg.lower():
                st.info("💡 **Facet Grid Issue**: Your grouping column has too many unique values. Try:\n"
                       "- Selecting a different grouping column with fewer categories\n"
                       "- Using 'Grouped Bar Chart' or 'Multiple Line Chart' instead\n"
                       "- Filtering your data to fewer categories")
            elif "sunburst" in error_msg.lower() or "treemap" in error_msg.lower():
                st.info("💡 **Hierarchy Issue**: Make sure your hierarchy columns don't contain empty values or ensure you have selected appropriate categorical columns")
            else:
                st.info("💡 Make sure you have selected appropriate columns for the chosen plot type")


# ══════════════════════════════════════════════════════════════════════════════
# 4. MAIN APPLICATION
# ══════════════════════════════════════════════════════════════════════════════


def main():
    """Main application logic"""
    
    # Sidebar navigation
    with st.sidebar:
        st.title("📊 Dashboard")
        st.divider()
        
        page = st.radio(
            "Navigation",
            ["📤 Upload Files", "➕ Create Dataset", "📊 Visualize"],
            label_visibility="collapsed"
        )
        
        st.divider()
        
        # Show uploaded files count
        if st.session_state.uploaded_files:
            st.metric("📂 Total Files", len(st.session_state.uploaded_files))
            if st.session_state.active_file:
                st.caption(f"Active: {st.session_state.active_file}")
        
        st.divider()
        st.caption("Combined Dashboard v2.0")
        st.caption("Python • Streamlit • Plotly")
    
    # Route to selected page
    if page == "📤 Upload Files":
        upload_files_page()
    elif page == "➕ Create Dataset":
        create_dataset_page()
    elif page == "📊 Visualize":
        visualize_page()

# ══════════════════════════════════════════════════════════════════════════════
# 5. RUN APPLICATION
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    main()
