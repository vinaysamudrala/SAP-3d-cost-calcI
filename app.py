import streamlit as st
import pandas as pd
import tempfile
import os
import cadquery as cq
import trimesh
import io

st.set_page_config(page_title="3D Cost Calculator", layout="wide")
st.title("3D Model Cost Calculator")

# --- Real-Time Tax Logic ---
# Streamlit uses "session state" to link variables together instantly.
if 'c_exc' not in st.session_state: st.session_state.c_exc = 0.00
if 'c_inc' not in st.session_state: st.session_state.c_inc = 0.00
if 'm_exc' not in st.session_state: st.session_state.m_exc = 0.00
if 'm_inc' not in st.session_state: st.session_state.m_inc = 0.00

def update_c_exc(): st.session_state.c_inc = st.session_state.c_exc * 1.18
def update_c_inc(): st.session_state.c_exc = st.session_state.c_inc / 1.18
def update_m_exc(): st.session_state.m_inc = st.session_state.m_exc * 1.18
def update_m_inc(): st.session_state.m_exc = st.session_state.m_inc / 1.18

# --- Pricing UI ---
st.header("Pricing per CC (18% Tax Rate)")
col1, col2 = st.columns(2)

with col1:
    st.subheader("Excluding Tax")
    st.number_input("Customer Price", min_value=0.0, format="%.2f", key="c_exc", on_change=update_c_exc)
    st.number_input("My Cost", min_value=0.0, format="%.2f", key="m_exc", on_change=update_m_exc)

with col2:
    st.subheader("Including 18% Tax")
    st.number_input("Customer Price (Inc Tax)", min_value=0.0, format="%.2f", key="c_inc", on_change=update_c_inc)
    st.number_input("My Cost (Inc Tax)", min_value=0.0, format="%.2f", key="m_inc", on_change=update_m_inc)

# --- File Upload & Quantities ---
st.header("Upload Files & Set Quantities")
uploaded_files = st.file_uploader("Upload 3D Models (.step, .stp, .obj, .stl)", accept_multiple_files=True)

qty_vars = {}
if uploaded_files:
    st.write("Set quantities for your uploaded files:")
    for f in uploaded_files:
        # Create a number input for each file dynamically
        qty_vars[f.name] = st.number_input(f"Qty: {f.name}", min_value=1, value=1, key=f"qty_{f.name}")

# --- Processing & Output ---
if uploaded_files:
    if st.button("Calculate & Generate Report", type="primary"):
        results = []
        t_qty = 0
        t_cc = 0.0
        t_cust_cost = 0.0
        t_my_cost = 0.0
        
        # Grab the current prices from the UI
        c_exc = st.session_state.c_exc
        c_inc = st.session_state.c_inc
        m_exc = st.session_state.m_exc
        m_inc = st.session_state.m_inc
        
        with st.spinner("Processing 3D models... Please wait."):
            # We use a temporary directory to safely load the uploaded files for CadQuery
            with tempfile.TemporaryDirectory() as temp_dir:
                for file in uploaded_files:
                    temp_path = os.path.join(temp_dir, file.name)
                    
                    # Save the uploaded browser file to the temporary local folder
                    with open(temp_path, "wb") as f:
                        f.write(file.getbuffer())
                        
                    ext = os.path.splitext(file.name)[1].lower()
                    volume_cc = 0.0
                    
                    try:
                        if ext in ['.step', '.stp']:
                            shape = cq.importers.importStep(temp_path)
                            solids = shape.solids().vals()
                            volume_cc = sum(solid.Volume() for solid in solids) / 1000.0
                        elif ext in ['.obj', '.stl']:
                            mesh = trimesh.load(temp_path, force='mesh')
                            volume_cc = mesh.volume / 1000.0
                            
                        qty = qty_vars[file.name]
                        total_cc = volume_cc * qty
                        
                        cust_unit_before = volume_cc * c_exc
                        cust_unit_after = volume_cc * c_inc
                        cust_total_after = total_cc * c_inc
                        
                        my_unit_before = volume_cc * m_exc
                        my_unit_after = volume_cc * m_inc
                        my_total_after = total_cc * m_inc
                        
                        t_qty += qty
                        t_cc += total_cc
                        t_cust_cost += cust_total_after
                        t_my_cost += my_total_after
                        
                        results.append({
                            "File name": file.name,
                            "Qty": qty,
                            "CC": round(volume_cc, 4),
                            "total CC": round(total_cc, 4),
                            "Unit price before tax": round(cust_unit_before, 2),
                            "Unit price after tax": round(cust_unit_after, 2),
                            "Total cost inc taxes": round(cust_total_after, 2),
                            "my Unit price before tax": round(my_unit_before, 2),
                            "my Unit price after tax": round(my_unit_after, 2),
                            "my Total cost inc taxes": round(my_total_after, 2)
                        })
                    except Exception as e:
                        st.error(f"Error processing {file.name}: {e}")

            # Add Grand Totals
            results.append({
                "File name": "GRAND TOTALS",
                "Qty": t_qty,
                "CC": "", 
                "total CC": round(t_cc, 4),
                "Unit price before tax": "",
                "Unit price after tax": "",
                "Total cost inc taxes": round(t_cust_cost, 2),
                "my Unit price before tax": "",
                "my Unit price after tax": "",
                "my Total cost inc taxes": round(t_my_cost, 2)
            })

            # Display Preview & Download Button
            if results:
                st.success("Calculations Complete!")
                df = pd.DataFrame(results)
                
                # Show a preview table in the browser
                st.dataframe(df)
                
                # Convert to CSV for downloading
                csv_data = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download CSV Report",
                    data=csv_data,
                    file_name="3D_Cost_Report.csv",
                    mime="text/csv",
                )