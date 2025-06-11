import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# Fungsi untuk membaca Google Sheets
def load_google_sheet(sheet_url):
    try:
        file_id = sheet_url.split("/d/")[1].split("/")[0]
        export_url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv"
        df = pd.read_csv(export_url)
        if 'Ticker' not in df.columns:
            st.error("Kolom 'Ticker' tidak ditemukan di Google Sheets.")
            return None
        return df
    except Exception as e:
        st.error(f"Gagal membaca Google Sheet: {e}")
        return None

# Ambil data dari Yahoo Finance
def get_stock_data(ticker, end_date):
    try:
        start_date = end_date - timedelta(days=90)
        stock = yf.Ticker(f"{ticker}.JK")
        data = stock.history(start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
        return data.tail(50) if not data.empty else None
    except Exception:
        return None

# === Indikator RSI Bullish Divergence ===
def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = delta.clip(lower=0).rolling(window=window).mean()
    loss = (-delta.clip(upper=0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(0)

def detect_rsi_bullish_divergence(data):
    rsi = calculate_rsi(data)
    close = data['Close']
    if len(rsi) < 15:
        return False
    low1 = close.iloc[-10:-5].idxmin()
    low2 = close.iloc[-5:].idxmin()
    if low1 >= low2:
        return False
    return close[low2] < close[low1] and rsi[low2] > rsi[low1]

# === Aplikasi Utama ===
def main():
    st.title("📈 Deteksi RSI Bullish Divergence Saham")

    sheet_url = st.text_input("Masukkan URL Google Sheets", value="https://docs.google.com/spreadsheets/d/1t6wgBIcPEUWMq40GdIH1GtZ8dvI9PZ2v/edit?usp=sharing")
    end_analysis_date = st.date_input("Tanggal Akhir Analisis", value=datetime.today())

    if st.button("Mulai Analisa"):
        df = load_google_sheet(sheet_url)
        if df is None:
            return

        tickers = df['Ticker'].dropna().unique().tolist()
        st.info(f"🔍 Menganalisis {len(tickers)} saham...")

        progress_bar = st.progress(0)
        results = []

        for i, ticker in enumerate(tickers):
            data = get_stock_data(ticker, end_analysis_date)
            if data is None or len(data) < 50:
                progress_bar.progress((i + 1) / len(tickers))
                continue

            if detect_rsi_bullish_divergence(data):
                results.append({
                    "Ticker": ticker,
                    "Last Close": round(data['Close'].iloc[-1], 2),
                    "Indikator": "RSI Bullish Divergence"
                })

            progress_bar.progress((i + 1) / len(tickers))

        if results:
            st.success("✅ Saham yang memenuhi RSI Bullish Divergence:")
            st.dataframe(pd.DataFrame(results))
        else:
            st.warning("❌ Tidak ada saham yang memenuhi RSI Bullish Divergence.")

if __name__ == "__main__":
    main()
