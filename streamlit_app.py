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

# === Indikator Teknikal ===
def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = delta.clip(lower=0).rolling(window=window).mean()
    loss = (-delta.clip(upper=0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(0)

def calculate_adi(data):
    clv = ((data['Close'] - data['Low']) - (data['High'] - data['Close'])) / (data['High'] - data['Low'])
    clv = clv.fillna(0)
    adi = (clv * data['Volume']).cumsum()
    return adi

def detect_accumulation(data):
    adi = calculate_adi(data)
    return adi.iloc[-1] > adi.iloc[-5]

def detect_distribution(data):
    adi = calculate_adi(data)
    return adi.iloc[-1] < adi.iloc[-5]

def detect_rsi_oversold(data):
    rsi = calculate_rsi(data)
    return rsi.iloc[-1] < 30 if not rsi.empty else False

def detect_rsi_exit_oversold(data):
    rsi = calculate_rsi(data)
    return rsi.iloc[-2] < 30 and rsi.iloc[-1] > 30 if len(rsi) >= 2 else False

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

def calculate_macd(data, fast=12, slow=26, signal=9):
    ema_fast = data['Close'].ewm(span=fast, adjust=False).mean()
    ema_slow = data['Close'].ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def detect_macd_bullish_crossover(data):
    macd, signal = calculate_macd(data)
    return macd.iloc[-2] < signal.iloc[-2] and macd.iloc[-1] > signal.iloc[-1]

def detect_macd_strong_bullish(data):
    macd, signal = calculate_macd(data)
    return detect_macd_bullish_crossover(data) and macd.iloc[-1] > 0

def detect_volume_up_two_days(data):
    if len(data) < 20:
        return False
    data = data.copy()
    data['MA20'] = data['Close'].rolling(20).mean()
    avg_volume_10d = data['Volume'].iloc[-11:-1].mean()
    return (data['Volume'].iloc[-1] > 1.5 * avg_volume_10d and
            data['Volume'].iloc[-2] > 1.3 * avg_volume_10d and
            data['Close'].iloc[-1] > data['MA20'].iloc[-1])

def detect_golden_cross(data):
    if len(data) < 50:
        return False
    data = data.copy()
    data['MA20'] = data['Close'].rolling(20).mean()
    data['MA50'] = data['Close'].rolling(50).mean()
    return data['MA20'].iloc[-2] < data['MA50'].iloc[-2] and data['MA20'].iloc[-1] > data['MA50'].iloc[-1]

# === Indikator Konsolidasi ===
def calculate_adx(data, period=14):
    high = data['High']
    low = data['Low']
    close = data['Close']

    plus_dm = high.diff()
    minus_dm = low.diff().abs()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)

    atr = tr.rolling(window=period).mean()
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.rolling(window=period).mean()
    return adx.fillna(0)

def detect_consolidation(data):
    if len(data) < 20:
        return False
    data = data.copy()
    data['MA20'] = data['Close'].rolling(20).mean()
    data['stddev'] = data['Close'].rolling(20).std()
    data['Upper'] = data['MA20'] + 2 * data['stddev']
    data['Lower'] = data['MA20'] - 2 * data['stddev']
    data['BandWidth'] = (data['Upper'] - data['Lower']) / data['MA20']

    adx = calculate_adx(data)

    last_3_bw = data['BandWidth'].iloc[-3:]
    last_3_adx = adx.iloc[-3:]

    return all(bw < 0.05 for bw in last_3_bw) and all(a < 20 for a in last_3_adx)

# === Aplikasi Utama ===
def main():
    st.title("📊 Analisa Saham - Google Sheets + Yahoo Finance")

    sheet_url = st.text_input("Masukkan URL Google Sheets", value="https://docs.google.com/spreadsheets/d/1t6wgBIcPEUWMq40GdIH1GtZ8dvI9PZ2v/edit?usp=sharing")
    end_analysis_date = st.date_input("Tanggal Akhir Analisis", value=datetime.today())

    st.sidebar.header("Pilih Indikator Analisis")
    rsi_check = st.sidebar.checkbox("RSI Oversold", value=True)
    rsi_exit_check = st.sidebar.checkbox("RSI Exit Oversold")
    rsi_div_check = st.sidebar.checkbox("RSI Bullish Divergence")
    macd_check = st.sidebar.checkbox("MACD Bullish", value=True)
    macd_strong_check = st.sidebar.checkbox("MACD Strong Bullish (>0)")
    volume_check = st.sidebar.checkbox("Volume Melejit (MA20 Confirmed)", value=True)
    golden_cross_check = st.sidebar.checkbox("Golden Cross")
    acc_check = st.sidebar.checkbox("Akumulasi")
    dist_check = st.sidebar.checkbox("Distribusi")
    cons_check = st.sidebar.checkbox("Konsolidasi (ADX<20 & BB squeeze)", value=True)
    three_of_kind_check = st.sidebar.checkbox("Three of Kind (RSI+MACD+Volume)")
    lengkap_check = st.sidebar.checkbox("Lengkap (Semua Indikator)")

    if st.button("Mulai Analisa"):
        selected_indicators = []
        if rsi_check: selected_indicators.append("RSI Oversold")
        if rsi_exit_check: selected_indicators.append("RSI Exit Oversold")
        if rsi_div_check: selected_indicators.append("RSI Bullish Divergence")
        if macd_check: selected_indicators.append("MACD Bullish")
        if macd_strong_check: selected_indicators.append("MACD Strong Bullish")
        if volume_check: selected_indicators.append("Volume Melejit (MA20 Confirmed)")
        if golden_cross_check: selected_indicators.append("Golden Cross")
        if acc_check: selected_indicators.append("Akumulasi")
        if dist_check: selected_indicators.append("Distribusi")
        if cons_check: selected_indicators.append("Konsolidasi")

        if three_of_kind_check:
            selected_indicators = ["RSI Oversold", "MACD Bullish", "Volume Melejit (MA20 Confirmed)"]
        if lengkap_check:
            selected_indicators = [
                "RSI Oversold", "RSI Exit Oversold", "RSI Bullish Divergence",
                "MACD Bullish", "MACD Strong Bullish",
                "Volume Melejit (MA20 Confirmed)", "Golden Cross", "Akumulasi", "Distribusi", "Konsolidasi"
            ]

        if not selected_indicators:
            st.error("Pilih minimal satu indikator!")
            return

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

            matched = []
            if detect_rsi_oversold(data): matched.append("RSI Oversold")
            if detect_rsi_exit_oversold(data): matched.append("RSI Exit Oversold")
            if detect_rsi_bullish_divergence(data): matched.append("RSI Bullish Divergence")
            if detect_macd_bullish_crossover(data): matched.append("MACD Bullish")
            if detect_macd_strong_bullish(data): matched.append("MACD Strong Bullish")
            if detect_volume_up_two_days(data): matched.append("Volume Melejit (MA20 Confirmed)")
            if detect_golden_cross(data): matched.append("Golden Cross")
            if detect_accumulation(data): matched.append("Akumulasi")
            if detect_distribution(data): matched.append("Distribusi")
            if detect_consolidation(data): matched.append("Konsolidasi")

            if all(ind in matched for ind in selected_indicators):
                results.append({
                    "Ticker": ticker,
                    "Last Close": round(data['Close'].iloc[-1], 2),
                    "Indikator Terpenuhi": ", ".join(matched)
                })

            progress_bar.progress((i + 1) / len(tickers))

        if results:
            st.success("✅ Saham yang memenuhi kriteria:")
            st.dataframe(pd.DataFrame(results))
        else:
            st.warning("❌ Tidak ada saham yang memenuhi kriteria.")

        st.subheader("🔎 Cek Data BBCA")
        bbca_data = get_stock_data("BBCA", end_analysis_date)
        if bbca_data is not None:
            st.dataframe(bbca_data.tail(50))
        else:
            st.error("❌ Gagal mengambil data BBCA.")

if __name__ == "__main__":
    main()
