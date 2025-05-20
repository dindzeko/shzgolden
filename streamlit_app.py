import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# === Fungsi untuk membaca Google Sheets ===
def load_google_sheets_csv(sheet_url):
    try:
        # Ambil file ID dari URL
        if "/d/" in sheet_url:
            file_id = sheet_url.split("/d/")[1].split("/")[0]
        else:
            raise ValueError("Format URL tidak dikenali")

        # Buat URL untuk export CSV
        export_url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv"

        df = pd.read_csv(export_url)

        if 'Ticker' not in df.columns:
            st.error("Kolom 'Ticker' tidak ditemukan pada Google Sheets.")
            return None

        return df
    except Exception as e:
        st.error(f"Error loading data from Google Sheets: {e}")
        return None

# === Ambil data harian dari Yahoo Finance ===
def get_stock_data(ticker, start_date, end_date):
    try:
        stock = yf.Ticker(f"{ticker}.JK")
        data = stock.history(start=start_date.strftime('%Y-%m-%d'),
                             end=end_date.strftime('%Y-%m-%d'))
        if len(data) < 4:
            return None
        return data
    except:
        return None

# === Indikator teknikal ===
def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def detect_golden_cross(data):
    if len(data) < 50:
        return False
    ma20 = data['Close'].rolling(20).mean()
    ma50 = data['Close'].rolling(50).mean()
    return ma20.iloc[-2] < ma50.iloc[-2] and ma20.iloc[-1] > ma50.iloc[-1]

def calculate_macd(data, fast=12, slow=26, signal=9):
    ema_fast = data['Close'].ewm(span=fast, adjust=False).mean()
    ema_slow = data['Close'].ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def detect_macd_bullish_crossover(data):
    macd, signal = calculate_macd(data)
    return len(macd) >= 2 and macd.iloc[-2] < signal.iloc[-2] and macd.iloc[-1] > signal.iloc[-1]

def detect_rsi_oversold(data):
    rsi = calculate_rsi(data)
    return len(rsi) > 0 and rsi.iloc[-1] < 30

def detect_volume_up_two_days(data):
    if len(data) < 2:
        return False
    return data['Volume'].iloc[-1] > data['Volume'].iloc[-2]

# === Main App ===
def main():
    st.title("📊 Analisa Saham Harian (Google Sheets Source)")

    sheet_url = st.text_input(
        "Masukkan URL Google Sheets",
        value="https://docs.google.com/spreadsheets/d/1t6wgBIcPEUWMq40GdIH1GtZ8dvI9PZ2v/edit?usp=sharing"
    )

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Tanggal Mulai Analisa", value=datetime.today() - timedelta(days=7))
    with col2:
        end_date = st.date_input("Tanggal Akhir Analisa", value=datetime.today())

    use_golden_cross = st.checkbox("Aktifkan Filter Golden Cross", value=True)

    if start_date > end_date:
        st.error("Tanggal mulai tidak boleh setelah tanggal akhir.")
        return

    if st.button("Mulai Analisa"):
        st.info("📥 Mengambil data dari Google Sheets...")
        df = load_google_sheets_csv(sheet_url)

        if df is None or 'Ticker' not in df.columns:
            return

        tickers = df['Ticker'].dropna().unique()
        total = len(tickers)
        progress = st.progress(0)
        log = st.empty()
        results = []

        for i, ticker in enumerate(tickers):
            data = get_stock_data(ticker, start_date, end_date)

            if data is None:
                progress.progress((i + 1) / total)
                continue

            criteria_met = []

            if use_golden_cross and detect_golden_cross(data):
                criteria_met.append("Golden Cross")
            if detect_rsi_oversold(data):
                criteria_met.append("RSI Oversold")
            if detect_macd_bullish_crossover(data):
                criteria_met.append("MACD Bullish")
            if detect_volume_up_two_days(data):
                criteria_met.append("Volume Naik 2 Hari")

            wajib = {"RSI Oversold", "MACD Bullish", "Volume Naik 2 Hari"}
            if wajib.issubset(set(criteria_met)):
                if not use_golden_cross or "Golden Cross" in criteria_met:
                    results.append({
                        "Ticker": ticker,
                        "Last Close": round(data['Close'].iloc[-1], 2),
                        "Criteria Matched": ", ".join(criteria_met)
                    })

            progress.progress((i + 1) / total)
            log.text(f"Progress: {i + 1} / {total} tickers")

        if results:
            st.success(f"✅ Ditemukan {len(results)} saham memenuhi kriteria")
            st.dataframe(pd.DataFrame(results))
        else:
            st.warning("❌ Tidak ada saham yang memenuhi kriteria.")

        # === Cek BBCA secara khusus ===
        st.subheader("🔎 Data BBCA (khusus)")

        bbca_data = get_stock_data("BBCA", start_date - timedelta(days=60), end_date)
        if bbca_data is not None and not bbca_data.empty:
            st.success("✅ Data BBCA berhasil diambil")
            st.dataframe(bbca_data.tail(50))
        else:
            st.error("❌ Gagal mengambil data BBCA")

if __name__ == "__main__":
    main()
