import streamlit as st
import subprocess

st.header("Daftar Library yang Terinstal")

# Jalankan perintah pip list
try:
    result = subprocess.run(["pip", "list"], capture_output=True, text=True)
    st.text_area("Library Terinstal", result.stdout, height=300)
except Exception as e:
    st.error(f"Error saat memeriksa library: {str(e)}")