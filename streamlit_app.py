import streamlit as st
import yfinance as yf
from datetime import datetime
import pandas as pd

# Judul aplikasi
st.title("📥 Pengambilan Data Historis Saham BEI")
st.markdown("Aplikasi ini mengambil data historis **150 hari perdagangan terakhir** untuk ticker berikut:")
st.markdown("- BBCA.JK (Bank Central Asia)\n- TLKM.JK (Telkom Indonesia)\n- SRTG.JK (Surya Toto Indonesia)")

# Daftar ticker lengkap dengan .JK
tickers = ["BBCA.JK", "TLKM.JK", "SRTG.JK"]

all_data = {}  # Dictionary untuk menyimpan semua data

progress_bar = st.progress(0)
status_text = st.empty()

for i, ticker in enumerate(tickers):
    try:
        status_text.text(f"Mengambil data untuk {ticker}...")

        # Menggunakan period="150d" agar ambil 150 hari perdagangan terakhir
        data = yf.download(ticker, period="150d", auto_adjust=True)

        if not data.empty:
            all_data[ticker] = data[['Open', 'High', 'Low', 'Close', 'Volume']]
            st.write(f"✅ {ticker}: {len(data)} hari perdagangan berhasil diambil")
        else:
            st.warning(f"Tidak ada data ditemukan untuk {ticker}")

    except Exception as e:
        st.error(f"Gagal mengambil data untuk {ticker}: {e}")
    
    # Update progress bar
    progress_bar.progress((i + 1) / len(tickers))

status_text.text("Selesai mengambil data.")

# Jika ada data berhasil diambil
if all_data:
    st.success("✅ Semua data berhasil diambil!")

    for ticker, data in all_data.items():
        st.subheader(f"📊 Data Historis {ticker}")
        st.dataframe(data.tail(20))  # Tampilkan 20 hari terakhir

        # Tombol download CSV
        csv = data.to_csv(index=True)
        st.download_button(
            label=f"⬇️ Unduh data {ticker}",
            data=csv,
            file_name=f"{ticker}_historical_data.csv",
            mime="text/csv"
        )
else:
    st.info("ℹ️ Tidak ada data berhasil diambil. Silakan cek koneksi atau ticker.")
