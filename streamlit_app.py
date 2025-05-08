import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import time

# Fungsi untuk membaca data dari Google Drive (file Excel)
def load_google_drive_excel(file_url):
    try:
        file_id = file_url.split("/d/")[1].split("/")[0]
        download_url = f"https://drive.google.com/uc?export=download&id= {file_id}"
        
        df = pd.read_excel(download_url, engine='openpyxl')
        
        if 'Ticker' not in df.columns:
            st.error("Kolom 'Ticker' tidak ditemukan dalam file Excel.")
            return None
        
        st.success(f"Data berhasil dimuat dari Google Drive!")
        st.info(f"Jumlah baris data: {len(df)}")
        st.info(f"Kolom dalam file Excel: {', '.join(df.columns)}")
        
        return df
    except Exception as e:
        st.error(f"Gagal memuat file Excel: {e}")
        return None

# Fungsi untuk mengambil data historis
def get_stock_data(ticker, end_date):
    try:
        stock = yf.Ticker(f"{ticker}.JK")
        start_date = end_date - timedelta(days=150)  # Ambil 150 hari ke belakang
        data = stock.history(start=start_date, end=end_date)
        
        if len(data) < 50:  # Minimal 50 hari data tersedia
            return None
            
        return data
    except Exception as e:
        st.error(f"Error mengambil data {ticker}: {str(e)}")
        return None

# Fungsi menghitung RSI
def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

# Fungsi untuk mendeteksi Golden Cross dan RSI
def check_signals(data):
    if data is None or len(data) < 50:
        return False, None, None, None
    
    # Hitung moving averages
    data['MA50'] = data['Close'].rolling(window=50).mean()
    data['MA100'] = data['Close'].rolling(window=100).mean()
    
    # Golden Cross condition
    current_ma50 = data['MA50'].iloc[-1]
    current_ma100 = data['MA100'].iloc[-2]
    prev_ma50 = data['MA50'].iloc[-2]
    prev_ma100 = data['MA100'].iloc[-2]
    
    golden_cross = (current_ma50 > current_ma100) and (prev_ma50 <= prev_ma100)
    
    # Hitung RSI
    rsi = calculate_rsi(data)
    
    return golden_cross, current_ma50, current_ma100, rsi

# Main function
def main():
    st.title("📈 Screening Saham - Golden Cross & RSI")

    # URL file Excel
    file_url = "https://docs.google.com/spreadsheets/d/1t6wgBIcPEUWMq40GdIH1GtZ8dvI9PZ2v/edit?usp=drive_link&ouid=106044501644618784207&rtpof=true&sd=true "

    # Load data
    st.info("Memuat data dari Google Drive...")
    df = load_google_drive_excel(file_url)
    if df is None or 'Ticker' not in df.columns:
        st.error("Gagal memuat data atau kolom 'Ticker' tidak ada")
        return

    tickers = df['Ticker'].tolist()
    total_tickers = len(tickers)

    # Input tanggal
    analysis_date = st.date_input("📅 Tanggal Analisis", value=datetime.today())

    if st.button("🔍 Mulai Analisis"):
        results = []
        failed_tickers = []  # Untuk menyimpan ticker yang gagal
        progress_bar = st.progress(0)
        progress_text = st.empty()

        # Variabel untuk data BBCA
        bbca_data = None

        for i, ticker in enumerate(tickers):
            data = get_stock_data(ticker, analysis_date)
            
            # Simpan data BBCA khusus
            if ticker == "BBCA":
                bbca_data = data

            if data is not None:
                golden_cross, ma50, ma100, rsi = check_signals(data)
                if golden_cross:
                    results.append({
                        "Ticker": ticker,
                        "MA50": round(ma50, 2),
                        "MA100": round(ma100, 2),
                        "RSI": round(rsi, 2),
                        "Signal": "Golden Cross"
                    })
            else:
                failed_tickers.append(ticker)  # Catat ticker yang gagal

            # Update progress
            progress = (i + 1) / total_tickers
            progress_bar.progress(progress)
            progress_text.text(f"Progress: {int(progress * 100)}%")

            # Jeda agar tidak kena limit API
            time.sleep(0.5)

        # Tampilkan hasil
        if results:
            st.subheader("✅ Hasil Screening Saham")
            results_df = pd.DataFrame(results)
            st.dataframe(results_df)
        else:
            st.info("❌ Tidak ada saham yang memenuhi kriteria Golden Cross")

        # Tampilkan ticker yang gagal (opsional)
        if failed_tickers:
            st.subheader("⚠️ Ticker yang Gagal Mendapatkan Data:")
            st.write(", ".join(failed_tickers))

        # Tampilkan data khusus BBCA
        st.subheader("📊 Analisis Khusus BBCA")
        if bbca_data is not None:
            golden_cross, ma50, ma100, rsi = check_signals(bbca_data)
            st.write(f"MA50 Terakhir: {round(ma50, 2)}")
            st.write(f"MA100 Terakhir: {round(ma100, 2)}")
            st.write(f"RSI(14): {round(rsi, 2) if rsi else 'N/A'}")

            if golden_cross:
                st.success("🎯 BBCA: Golden Cross terdeteksi!")
            else:
                st.warning("❗ BBCA: Golden Cross tidak terdeteksi")
        else:
            st.warning("⚠️ Tidak ada data untuk BBCA")

if __name__ == "__main__":
    main()
