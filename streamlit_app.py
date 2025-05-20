import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# Fungsi untuk membaca data dari Google Drive (file Excel)
def load_google_drive_excel(file_url):
    try:
        file_id = file_url.split("/d/")[1].split("/")[0]
        download_url = f"https://drive.google.com/uc?export=download&id= {file_id}"
        df = pd.read_excel(download_url, engine='openpyxl')

        if 'Ticker' not in df.columns:
            st.error("The 'Ticker' column is missing in the Excel file.")
            return None

        return df
    except Exception as e:
        st.error(f"Error loading Excel file from Google Drive: {e}")
        return None

# Ambil data harian dari Yahoo Finance
def get_stock_data(ticker, start_date, end_date):
    try:
        stock = yf.Ticker(f"{ticker}.JK")
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        data = stock.history(start=start_date_str, end=end_date_str)

        if len(data) < 4:
            return None

        return data
    except Exception as e:
        return None

# Hitung Simple Moving Average
def calculate_sma(data, window=20):
    return data['Close'].rolling(window=window).mean()

# Hitung RSI
def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# Deteksi Golden Cross
def detect_golden_cross(data):
    if len(data) < 50:
        return False
    data = data.copy()
    data['MA20'] = data['Close'].rolling(20).mean()
    data['MA50'] = data['Close'].rolling(50).mean()
    return data['MA20'].iloc[-2] < data['MA50'].iloc[-2] and data['MA20'].iloc[-1] > data['MA50'].iloc[-1]

# Deteksi RSI Oversold
def detect_rsi_oversold(data):
    rsi = calculate_rsi(data)
    return len(rsi) > 0 and rsi.iloc[-1] < 30

# Deteksi MACD Bullish Crossover
def calculate_macd(data, fast=12, slow=26, signal=9):
    ema_fast = data['Close'].ewm(span=fast, min_periods=0, adjust=False).mean()
    ema_slow = data['Close'].ewm(span=slow, min_periods=0, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, min_periods=0, adjust=False).mean()
    return macd, signal_line

def detect_macd_bullish_crossover(data):
    macd, signal = calculate_macd(data)
    if len(macd) < 2:
        return False
    return (macd.iloc[-2] < signal.iloc[-2] and macd.iloc[-1] > signal.iloc[-1])

# Deteksi Volume Naik 2 Hari Berturut-turut
def detect_volume_up_two_days(data):
    if len(data) < 2:
        return False
    return data['Volume'].iloc[-1] > data['Volume'].iloc[-2]

# Main function
def main():
    st.title("📊 Analisa Style 2")

    # URL file Excel di Google Drive
    file_url = st.text_input(
        "Masukkan URL Google Sheets",
        value="https://docs.google.com/spreadsheets/d/1t6wgBIcPEUWMq40GdIH1GtZ8dvI9PZ2v/edit?usp=drive_link&ouid=106044501644618784207&rtpof=true&sd=true "
    )

    col1, col2 = st.columns(2)
    with col1:
        start_analysis_date = st.date_input("Tanggal Mulai Analisis", value=datetime.today() - timedelta(days=7))
    with col2:
        end_analysis_date = st.date_input("Tanggal Akhir Analisis", value=datetime.today())

    use_golden_cross = st.checkbox("Aktifkan Filter Golden Cross", value=True)

    if start_analysis_date > end_analysis_date:
        st.error("Tanggal mulai tidak boleh lebih besar dari tanggal akhir.")
        return

    if st.button("Mulai Analisa"):
        st.info("Loading data from Google Drive...")
        df = load_google_drive_excel(file_url)

        if df is None or 'Ticker' not in df.columns:
            st.error("Failed to load data or 'Ticker' column is missing.")
            return

        tickers = df['Ticker'].tolist()
        total_tickers = len(tickers)

        progress_bar = st.progress(0)
        progress_text = st.empty()

        matches = []

        for i, ticker in enumerate(tickers):
            data = get_stock_data(ticker, start_analysis_date, end_analysis_date)

            if data is None:
                progress = (i + 1) / total_tickers
                progress_bar.progress(progress)
                progress_text.text(f"Progress: {int(progress * 100)}%")
                continue

            criteria_met = []
            required_criteria = ["RSI Oversold", "MACD Bullish", "Volume Naik 2 Hari"]

            if use_golden_cross and detect_golden_cross(data):
                criteria_met.append("Golden Cross")
            if detect_rsi_oversold(data):
                criteria_met.append("RSI Oversold")
            if detect_macd_bullish_crossover(data):
                criteria_met.append("MACD Bullish")
            if detect_volume_up_two_days(data):
                criteria_met.append("Volume Naik 2 Hari")

            # Pastikan semua kriteria wajib terpenuhi
            if all(req in criteria_met for req in required_criteria):
                if use_golden_cross:
                    if "Golden Cross" in criteria_met:
                        matches.append({
                            "Ticker": ticker,
                            "Last Close": round(data['Close'].iloc[-1], 2),
                            "Criteria Matched": ", ".join(criteria_met)
                        })
                else:
                    matches.append({
                        "Ticker": ticker,
                        "Last Close": round(data['Close'].iloc[-1], 2),
                        "Criteria Matched": ", ".join(criteria_met)
                    })

            # Update progress bar
            progress = (i + 1) / total_tickers
            progress_bar.progress(progress)
            progress_text.text(f"Progress: {int(progress * 100)}%")

        if matches:
            st.subheader("✅ Saham Memenuhi Kriteria:")
            results_df = pd.DataFrame(matches)
            st.dataframe(results_df)
        else:
            st.info("❌ Tidak ada saham yang memenuhi kriteria.")

        # === BAGIAN TEST DATA BBCA ===
        st.subheader("📎 Separate Result for BBCA")

        # Ambil data BBCA minimal 50 hari sebelum tanggal analisa
        bbc_data = get_stock_data("BBCA",
                                  start_analysis_date - timedelta(days=60),  # Jaminan 50 hari perdagangan
                                  end_analysis_date)

        if bbc_data is not None and not bbc_data.empty:
            st.write("✅ Data Retrieved for BBCA:")

            # Tampilkan maksimal 50 bar
            if len(bbc_data) >= 50:
                st.dataframe(bbc_data.tail(50))
                st.success(f"📊 Berhasil mengambil {len(bbc_data)} hari data BBCA (cukup untuk analisa teknikal)")
            else:
                st.warning(f"⚠️ Hanya ada {len(bbc_data)} hari data BBCA (kurang dari 50 hari perdagangan)")

            # Info rentang tanggal
            st.info(f"Rentang tanggal data: {bbc_data.index.min().strftime('%Y-%m-%d')} hingga {bbc_data.index.max().strftime('%Y-%m-%d')}")
        else:
            st.error("❌ Gagal mengambil data untuk BBCA.")

if __name__ == "__main__":
    main()
