import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# Fungsi untuk membaca Google Sheets (format CSV)
def load_google_sheet_csv(csv_url):
    try:
        df = pd.read_csv(csv_url)
        if 'Ticker' not in df.columns:
            st.error("Kolom 'Ticker' tidak ditemukan.")
            return None
        return df
    except Exception as e:
        st.error(f"Error membaca Google Sheet: {e}")
        return None

# Fungsi ambil data saham
def get_stock_data(ticker, end_date, days=50):
    try:
        start_date = end_date - timedelta(days=100)
        stock = yf.Ticker(f"{ticker}.JK")
        data = stock.history(start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
        if len(data) >= days:
            return data.tail(days)
        else:
            return None
    except Exception:
        return None

# Indikator
def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=window).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(data, fast=12, slow=26, signal=9):
    ema_fast = data['Close'].ewm(span=fast, adjust=False).mean()
    ema_slow = data['Close'].ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def detect_rsi_oversold(data):
    rsi = calculate_rsi(data)
    return rsi.iloc[-1] < 30 if not rsi.isna().all() else False

def detect_macd_bullish_crossover(data):
    macd, signal = calculate_macd(data)
    return macd.iloc[-2] < signal.iloc[-2] and macd.iloc[-1] > signal.iloc[-1]

def detect_volume_up_two_days(data):
    return data['Volume'].iloc[-1] > data['Volume'].iloc[-2]

def detect_golden_cross(data):
    ma20 = data['Close'].rolling(window=20).mean()
    ma50 = data['Close'].rolling(window=50).mean()
    return ma20.iloc[-2] < ma50.iloc[-2] and ma20.iloc[-1] > ma50.iloc[-1]

# Main App
def main():
    st.title("📊 Analisa Saham - Pilih Kriteria")

    csv_url = st.text_input("Masukkan URL CSV Google Sheets", 
        value="https://docs.google.com/spreadsheets/d/e/2PACX-1vT.../pub?output=csv")

    end_date = st.date_input("Tanggal Akhir Analisis", value=datetime.today())

    # Pilihan Checkbox
    st.subheader("Pilih Kriteria Analisa:")
    chk_rsi = st.checkbox("✅ RSI Oversold")
    chk_macd = st.checkbox("✅ MACD Bullish Crossover")
    chk_gc = st.checkbox("✅ Golden Cross")
    chk_three = st.checkbox("✅ Three of Kind (RSI + MACD + Volume)")
    chk_all = st.checkbox("✅ Lengkap (Golden Cross + RSI + MACD + Volume)")

    if st.button("Mulai Analisa"):
        df = load_google_sheet_csv(csv_url)
        if df is None:
            return

        tickers = df['Ticker'].dropna().unique().tolist()
        st.info(f"📈 Memulai analisa {len(tickers)} saham...")
        matches = []
        progress_bar = st.progress(0)

        for i, ticker in enumerate(tickers):
            data = get_stock_data(ticker, end_date)
            if data is None:
                progress_bar.progress((i + 1) / len(tickers))
                continue

            # Evaluasi indikator
            rsi_ok = detect_rsi_oversold(data)
            macd_ok = detect_macd_bullish_crossover(data)
            volume_ok = detect_volume_up_two_days(data)
            gc_ok = detect_golden_cross(data)

            match = False
            alasan = []

            # Logika seleksi berdasarkan checkbox
            if chk_all and all([rsi_ok, macd_ok, volume_ok, gc_ok]):
                match = True
                alasan.append("Lengkap")
            elif chk_three and all([rsi_ok, macd_ok, volume_ok]):
                match = True
                alasan.append("Three of Kind")
            else:
                if chk_rsi and not rsi_ok:
                    match = False
                elif chk_rsi:
                    match = True
                    alasan.append("RSI")

                if chk_macd and not macd_ok:
                    match = False
                elif chk_macd:
                    match = True
                    alasan.append("MACD")

                if chk_gc and not gc_ok:
                    match = False
                elif chk_gc:
                    match = True
                    alasan.append("Golden Cross")

            if match:
                matches.append({
                    "Ticker": ticker,
                    "Last Close": data['Close'].iloc[-1],
                    "Kriteria Terpenuhi": ", ".join(alasan)
                })

            progress_bar.progress((i + 1) / len(tickers))

        if matches:
            st.success("✅ Saham yang memenuhi kriteria:")
            st.dataframe(pd.DataFrame(matches))
        else:
            st.warning("❌ Tidak ada saham yang memenuhi kriteria.")

if __name__ == "__main__":
    main()
