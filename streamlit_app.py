import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# Fungsi untuk membaca data dari Google Sheets
def load_google_sheet_csv(sheet_url):
    try:
        sheet_url = sheet_url.strip().replace(" ", "")
        # Ekstrak ID dan gid dari URL
        if "/d/" in sheet_url:
            file_id = sheet_url.split("/d/")[1].split("/")[0]
        else:
            st.error("URL Google Sheet tidak valid.")
            return None

        if "gid=" in sheet_url:
            gid = sheet_url.split("gid=")[-1].split("&")[0]
        else:
            gid = "0"

        download_url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv&gid={gid}"
        df = pd.read_csv(download_url)

        if 'Ticker' not in df.columns:
            st.error("Kolom 'Ticker' tidak ditemukan.")
            return None

        return df
    except Exception as e:
        st.error(f"Error loading Google Sheet: {e}")
        return None

# Ambil data harian dari Yahoo Finance
def get_stock_data(ticker, start_date, end_date):
    try:
        stock = yf.Ticker(f"{ticker}.JK")
        data = stock.history(start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
        return data if len(data) >= 4 else None
    except:
        return None

# Indikator teknikal
def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = delta.clip(lower=0).rolling(window=window).mean()
    loss = -delta.clip(upper=0).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def detect_rsi_oversold(data):
    rsi = calculate_rsi(data)
    return not rsi.empty and rsi.iloc[-1] < 30

def calculate_macd(data, fast=12, slow=26, signal=9):
    ema_fast = data['Close'].ewm(span=fast, adjust=False).mean()
    ema_slow = data['Close'].ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def detect_macd_bullish_crossover(data):
    macd, signal = calculate_macd(data)
    return len(macd) >= 2 and macd.iloc[-2] < signal.iloc[-2] and macd.iloc[-1] > signal.iloc[-1]

def detect_volume_up_two_days(data):
    return len(data) >= 2 and data['Volume'].iloc[-1] > data['Volume'].iloc[-2]

def detect_golden_cross(data):
    if len(data) < 50:
        return False
    data['MA20'] = data['Close'].rolling(20).mean()
    data['MA50'] = data['Close'].rolling(50).mean()
    return data['MA20'].iloc[-2] < data['MA50'].iloc[-2] and data['MA20'].iloc[-1] > data['MA50'].iloc[-1]

# Aplikasi utama
def main():
    st.title("📊 Analisa Saham Otomatis dari Google Sheet")

    sheet_url = st.text_input("Masukkan URL Google Sheets", 
        "https://docs.google.com/spreadsheets/d/1t6wgBIcPEUWMq40GdIH1GtZ8dvI9PZ2v/edit?gid=1445483445")

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Tanggal Mulai", value=datetime.today() - timedelta(days=7))
    with col2:
        end_date = st.date_input("Tanggal Akhir", value=datetime.today())

    use_golden_cross = st.checkbox("Gunakan Filter Golden Cross", value=True)

    if st.button("🔍 Mulai Analisa"):
        st.info("📥 Mengambil data dari Google Sheet...")
        df = load_google_sheet_csv(sheet_url)

        if df is None:
            return

        tickers = df['Ticker'].dropna().astype(str).tolist()
        matches = []
        progress = st.progress(0)
        status = st.empty()

        for i, ticker in enumerate(tickers):
            data = get_stock_data(ticker, start_date, end_date)
            if data is None:
                continue

            criteria_met = []
            required = ["RSI Oversold", "MACD Bullish", "Volume Naik 2 Hari"]

            if use_golden_cross and detect_golden_cross(data):
                criteria_met.append("Golden Cross")
            if detect_rsi_oversold(data):
                criteria_met.append("RSI Oversold")
            if detect_macd_bullish_crossover(data):
                criteria_met.append("MACD Bullish")
            if detect_volume_up_two_days(data):
                criteria_met.append("Volume Naik 2 Hari")

            if all(req in criteria_met for req in required):
                if not use_golden_cross or "Golden Cross" in criteria_met:
                    matches.append({
                        "Ticker": ticker,
                        "Last Close": round(data['Close'].iloc[-1], 2),
                        "Criteria": ", ".join(criteria_met)
                    })

            progress.progress((i + 1) / len(tickers))
            status.text(f"Progress: {i + 1}/{len(tickers)}")

        if matches:
            st.success("✅ Saham yang memenuhi kriteria:")
            st.dataframe(pd.DataFrame(matches))
        else:
            st.warning("❌ Tidak ada saham yang memenuhi kriteria.")

if __name__ == "__main__":
    main()
