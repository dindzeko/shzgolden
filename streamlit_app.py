import streamlit as st
import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd

# Judul aplikasi
st.title("📥 Pengambilan Data Historis Saham")
st.markdown("Masukkan ticker saham BEI (tanpa `.JK`) untuk mengambil data historis 150 hari terakhir.")

# Input ticker oleh pengguna
default_tickers = "SRTG, BBCA, TLKM"
tickers_input = st.text_input("Ticker Saham (pisahkan dengan koma)", default_tickers)

# Tombol untuk mulai ambil data
if st.button("🔁 Ambil Data"):
    tickers = [ticker.strip() for ticker in tickers_input.split(",")]
    
    # Tanggal akhir dan awal
    end_date = datetime.today()
    start_date = end_date - timedelta(days=150)  # 150 hari kalender ≈ ~110–120 hari perdagangan
    
    all_data = {}  # Dictionary untuk menyimpan semua data

    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, ticker in enumerate(tickers):
        try:
            full_ticker = f"{ticker}.JK"  # Tambahkan .JK untuk pasar BEI
            status_text.text(f"Mengambil data untuk {full_ticker}...")

            # Ambil data dari Yahoo Finance
            data = yf.download(full_ticker, start=start_date, end=end_date)

            if not data.empty:
                all_data[ticker] = data[['Open', 'High', 'Low', 'Close', 'Volume']]
            else:
                st.warning(f"Tidak ada data ditemukan untuk {full_ticker}")

        except Exception as e:
            st.error(f"Gagal mengambil data untuk {ticker}: {e}")
        
        # Update progress bar
        progress_bar.progress((i + 1) / len(tickers))

    status_text.text("Selesai mengambil data.")

    # Jika ada data berhasil diambil
    if all_data:
        st.success("✅ Data berhasil diambil!")

        # Tampilkan dan simpan setiap ticker
        for ticker, data in all_data.items():
            st.subheader(f"📊 Data Historis {ticker}.JK")
            st.dataframe(data.tail(20))  # Tampilkan 20 hari terakhir

            # Tombol download CSV
            csv = data.to_csv(index=True)
            st.download_button(
                label=f"⬇️ Unduh data {ticker}.JK",
                data=csv,
                file_name=f"{ticker}_historical_data.csv",
                mime="text/csv"
            )
    else:
        st.info("ℹ️ Tidak ada data berhasil diambil. Silakan periksa ticker atau koneksi internet.")
