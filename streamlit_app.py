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

# Indikator teknikal
def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = delta.clip(lower=0).rolling(window=window).mean()
    loss = (-delta.clip(upper=0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(0)

def detect_rsi_oversold(data):
    rsi = calculate_rsi(data)
    if rsi.empty or pd.isna(rsi.iloc[-1]):
        return False
    return rsi.iloc[-1] < 30

def calculate_macd(data, fast=12, slow=26, signal=9):
    ema_fast = data['Close'].ewm(span=fast, adjust=False).mean()
    ema_slow = data['Close'].ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def detect_macd_bullish_crossover(data):
    macd, signal = calculate_macd(data)
    if len(macd) < 2:
        return False
    return macd.iloc[-2] < signal.iloc[-2] and macd.iloc[-1] > signal.iloc[-1]

def detect_volume_up_two_days(data):
    if len(data) < 2:
        return False
    return data['Volume'].iloc[-1] > data['Volume'].iloc[-2]

def detect_golden_cross(data):
    if len(data) < 50:
        return False
    data = data.copy()
    data['MA20'] = data['Close'].rolling(20).mean()
    data['MA50'] = data['Close'].rolling(50).mean()
    return data['MA20'].iloc[-2] < data['MA50'].iloc[-2] and data['MA20'].iloc[-1] > data['MA50'].iloc[-1]

# Aplikasi utama
def main():
    st.title("📊 Analisa Saham - Google Sheets + Yahoo Finance")

    sheet_url = st.text_input(
        "Masukkan URL Google Sheets",
        value="https://docs.google.com/spreadsheets/d/1t6wgBIcPEUWMq40GdIH1GtZ8dvI9PZ2v/edit?usp=sharing"
    )

    end_analysis_date = st.date_input("Tanggal Akhir Analisis", value=datetime.today())
    use_golden_cross = st.checkbox("Aktifkan Filter Golden Cross", value=True)

    if st.button("Mulai Analisa"):
        df = load_google_sheet(sheet_url)
        if df is None:
            return

        tickers = df['Ticker'].dropna().unique().tolist()
        total = len(tickers)
        st.info(f"🔍 Menganalisis {total} saham...")

        progress_bar = st.progress(0)
        progress_text = st.empty()
        results = []

        for i, ticker in enumerate(tickers):
            data = get_stock_data(ticker, end_analysis_date)

            if data is None or len(data) < 50:
                progress_bar.progress((i + 1) / total)
                continue

            matched = []
            if detect_rsi_oversold(data):
                matched.append("RSI Oversold")
            if detect_macd_bullish_crossover(data):
                matched.append("MACD Bullish")
            if detect_volume_up_two_days(data):
                matched.append("Volume Naik 2 Hari")
            if use_golden_cross and detect_golden_cross(data):
                matched.append("Golden Cross")

            wajib = {"RSI Oversold", "MACD Bullish", "Volume Naik 2 Hari"}
            if wajib.issubset(set(matched)):
                if use_golden_cross and "Golden Cross" in matched or not use_golden_cross:
                    results.append({
                        "Ticker": ticker,
                        "Last Close": round(data['Close'].iloc[-1], 2),
                        "Matched": ", ".join(matched)
                    })

            progress = (i + 1) / total
            progress_bar.progress(progress)
            progress_text.text(f"Progress: {int(progress * 100)}%")

        if results:
            st.success("✅ Saham yang memenuhi kriteria:")
            st.dataframe(pd.DataFrame(results))
        else:
            st.warning("❌ Tidak ada saham yang memenuhi kriteria.")

        # Analisis khusus BBCA
        st.subheader("🔎 Cek Data BBCA")
        bbca_data = get_stock_data("BBCA", end_analysis_date)

        if bbca_data is not None and not bbca_data.empty:
            st.write(f"📊 Menampilkan {len(bbca_data)} hari terakhir data BBCA")
            st.dataframe(bbca_data.tail(50))
        else:
            st.error("❌ Gagal mengambil data BBCA.")

if __name__ == "__main__":
    main()
