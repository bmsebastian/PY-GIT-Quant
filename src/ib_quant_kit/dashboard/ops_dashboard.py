import streamlit as st
import json, os

st.set_page_config(page_title="IB Quant Ops", layout="wide")
st.title("IB Quant Ops Dashboard (Lite)")

# Positions
st.header("Positions")
st.write("Positions are kept in-memory in runtime; hook to your process via API or shared storage.")

# Fills
st.header("Fills")
fills_path = "./runtime/fills.jsonl"
if os.path.exists(fills_path):
    with open(fills_path, "r", encoding="utf-8") as f:
        lines = [json.loads(x) for x in f if x.strip()]
    st.dataframe(lines)
else:
    st.info("No fills yet.")
