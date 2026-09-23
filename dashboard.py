# dashboard.py
import streamlit as st
import sqlite3
import pandas as pd
import httpx
from pathlib import Path

st.set_page_config(page_title="PulseCheck OS Command Center", layout="wide")
st.title("🛡️ PulseCheck OS: Live Operational Matrix")

DB_PATH = "pulsecheck_state.db"

def fetch_pipeline_state():
    if not Path(DB_PATH).exists(): return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    try:
        # Using exact column names from your schema
        df = pd.read_sql_query("SELECT loop_identifier, execution_status, last_modified FROM loop_execution_state ORDER BY last_modified ASC", conn)
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()
    return df

st.header("1. Pipeline Execution Trace")
df = fetch_pipeline_state()

if df.empty:
    st.warning("Database empty or schema missing. Run `python main.py` to trigger the pipeline.")
else:
    # Safely wrap columns: 4 items per row for the 12 loops
    chunks = [df.iloc[i:i + 4] for i in range(0, len(df), 4)]
    for chunk in chunks:
        cols = st.columns(4)
        for idx, (index, row) in enumerate(chunk.iterrows()):
            with cols[idx]:
                loop_name = row['loop_identifier'].split('_')[0]
                # Referencing execution_status instead of status
                if row['execution_status'] == "FAILED":
                    st.error(f"**{loop_name}**\n\nFAILED")
                else:
                    st.success(f"**{loop_name}**\n\n{row['execution_status']}")

    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        st.header("2. Live API State Verification")
        st.caption("Querying mock APIs in real-time...")
        
        try:
            order_res = httpx.get("http://localhost:4001/state", timeout=2.0).json()
            billing_res = httpx.get("http://localhost:4002/state", timeout=2.0).json()
            erp_res = httpx.get("http://localhost:4003/state", timeout=2.0).json()
            
            order_status = order_res.get("orders", [{}])[0].get("status", "UNKNOWN")
            billing_status = billing_res.get("payments", [{}])[0].get("status", "UNKNOWN")
            erp_triggered = len(erp_res.get("fulfillments", [])) > 0
            
            st.metric(label="Order Status (Port 4001)", value=order_status, delta="Converged" if order_status == "PAID" else "-")
            st.metric(label="Billing Capture (Port 4002)", value=billing_status, delta="Reconciled" if billing_status == "PAID" else "-")
            st.metric(label="ERP Dispatch (Port 4003)", value=str(erp_triggered), delta="Resolved" if erp_triggered else "-")
        except Exception as e:
            st.error(f"Failed to reach mock microservices: {e}\nEnsure `start_all.sh` is running.")

    with col2:
        st.header("3. System Artifacts")
        tab1, tab2 = st.tabs(["Routing Policy (L12)", "Post-Mortem (L10)"])
        
        with tab1:
            yaml_file = Path("routing.yaml")
            if yaml_file.exists(): 
                st.code(yaml_file.read_text(), language="yaml")
            else: 
                st.info("No routing rules generated yet.")
            
        with tab2:
            pm_files = list(Path("incident_reports").glob("*.md"))
            if pm_files: 
                st.markdown(pm_files[-1].read_text())
            else: 
                st.info("Post-mortem generation pending...")