import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# === Fungsi untuk membaca Google Sheet sebagai CSV ===
def load_google_sheet_csv(sheet_url):
    try:
        # Ekstrak ID dari URL
        if "/d/" not in sheet_url:
            st.error("URL Google Sheet tidak valid.")
            return None

        sheet_id = sheet_url.split("/d/")[1].split("/")[0]
        gid = "0"
        if "gid=" in sheet_url:
            gid = sheet_url.split("gid=")[-1].split("#")[0]

        csv_url = f"https://docs.google.com/spreadsheets/d/ {sheet_id}/export?format=csv&gid={gid}"
        df = pd.read_csv(csv_url)

        if 'Ticker' not in df.columns:
            st.error("Kolom 'Ticker' tidak ditemukan di Google Sheet.")
            return None

        return df
    except Exception as e:
        st.error(f"❌ Gagal membaca Google Sheet: {e}")
        return None

# === Ambil data saham dari Yahoo Finance ===
def get_stock_data(ticker, end_date):
    start_date = end_date - timedelta(days=60)
    try:
        data = yf.download(f"{ticker}.JK", start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
        if data.empty or len(data) < 20:
            return None
        return data.tail(50)  # Hanya ambil 50 hari perdagangan terakhir
    except Exception as e:
        return None

# === Indikator Teknikal ===

def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = (delta.clip(lower=0)).rolling(window=window).mean()
    loss = (-delta.clip(upper=0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def detect_rsi_oversold(data):
    rsi = calculate_rsi(data)
    if rsi.empty or rsi.isna().all():
        return False
    return rsi.iloc[-1] < 30

def calculate_macd(data, fast=12, slow=26, signal=9):
    ema_fast = data['Close'].ewm(span=fast, adjust=False).mean()
    ema_slow = data['Close'].ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def detect_macd_bullish_crossover(data):
    if len(data) < 2:
        return False
    macd, signal = calculate_macd(data)
    if macd.empty or signal.empty:
        return False
    return (macd.iloc[-2] < signal.iloc[-2]) and (macd.iloc[-1] > signal.iloc[-1])

def detect_volume_up_two_days(data):
    if len(data) < 2:
        return False
    return data['Volume'].iloc[-1] > data['Volume'].iloc[-2]

def detect_golden_cross(data):
    if len(data) < 50:
        return False
    ma20 = data['Close'].rolling(20).mean()
    ma50 = data['Close'].rolling(50).mean()
    if ma20.empty or ma50.empty:
        return False
    return (ma20.iloc[-2] < ma50.iloc[-2]) and (ma20.iloc[-1] > ma50.iloc[-1])

# === Streamlit App ===
def main():
    st.title("📊 Analisa Saham dari Google Sheets")
    st.markdown("🚀 Input URL Google Sheet dan tanggal akhir analisa. Data saham akan dianalisis selama 2 bulan terakhir (maksimal 50 hari perdagangan).")

    # Input
    sheet_url = st.text_input("Masukkan URL Google Sheet", 
        "https://docs.google.com/spreadsheets/d/1t6wgBIcPEUWMq40GdIH1GtZ8dvI9PZ2v/edit?gid=1445483445 ")
    
    end_date = st.date_input("Tanggal Akhir Analisis", value=datetime.today())
    use_golden_cross = st.checkbox("Gunakan Filter Golden Cross", value=True)

    if st.button("🔍 Mulai Analisa"):
        st.info("📥 Membaca data dari Google Sheet...")
        df = load_google_sheet_csv(sheet_url)

        if df is None:
            return

        tickers = df['Ticker'].dropna().astype(str).tolist()
        total = len(tickers)

        progress = st.progress(0)
        status = st.empty()
        hasil = []

        for i, ticker in enumerate(tickers):
            data = get_stock_data(ticker, end_date)
            if data is None or len(data) < 20:
                continue

            criteria = []
            wajib = ["RSI Oversold", "MACD Bullish", "Volume Naik 2 Hari"]

            if use_golden_cross and detect_golden_cross(data):
                criteria.append("Golden Cross")
            if detect_rsi_oversold(data):
                criteria.append("RSI Oversold")
            if detect_macd_bullish_crossover(data):
                criteria.append("MACD Bullish")
            if detect_volume_up_two_days(data):
                criteria.append("Volume Naik 2 Hari")

            if all(k in criteria for k in wajib):
                if not use_golden_cross or "Golden Cross" in criteria:
                    hasil.append({
                        "Ticker": ticker,
                        "Last Close": round(data['Close'].iloc[-1], 2),
                        "Criteria": ", ".join(criteria)
                    })

            progress.progress((i + 1) / total)
            status.text(f"Proses: {i + 1}/{total} saham")

        if hasil:
            st.success("✅ Saham yang memenuhi kriteria:")
            st.dataframe(pd.DataFrame(hasil))
        else:
            st.warning("❌ Tidak ada saham yang memenuhi kriteria.")

        # === Cek BBCA sebagai contoh ===
        st.subheader("📌 Contoh Saham: BBCA")
        bbca_data = get_stock_data("BBCA", end_date)
        if bbca_data is not None and not bbca_data.empty:
            st.dataframe(bbca_data[['Open', 'High', 'Low', 'Close', 'Volume']].tail(10))
        else:
            st.error("Gagal mengambil data BBCA.")

if __name__ == "__main__":
    main()
