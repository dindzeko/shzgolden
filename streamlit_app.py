import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# === Fungsi Load Google Sheet ===
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

# === Ambil data saham dari Yahoo Finance ===
def get_stock_data(ticker, end_date):
    try:
        start_date = end_date - timedelta(days=90)
        stock = yf.Ticker(f"{ticker}.JK")
        data = stock.history(start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
        return data if not data.empty else None
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

# === Indikator MFI ===
def calculate_mfi(data, window=14):
    typical_price = (data['High'] + data['Low'] + data['Close']) / 3
    money_flow = typical_price * data['Volume']
    positive_flow = []
    negative_flow = []

    for i in range(1, len(typical_price)):
        if typical_price[i] > typical_price[i-1]:
            positive_flow.append(money_flow[i])
            negative_flow.append(0)
        else:
            positive_flow.append(0)
            negative_flow.append(money_flow[i])

    pos_mf = pd.Series(positive_flow).rolling(window=window).sum()
    neg_mf = pd.Series(negative_flow).rolling(window=window).sum()

    mfi = 100 - (100 / (1 + (pos_mf / neg_mf)))
    mfi.index = data.index[1:]  # geser index karena mulai dari i=1
    return mfi

def detect_mfi_signal(data):
    mfi = calculate_mfi(data)
    if len(mfi) == 0 or pd.isna(mfi.iloc[-1]):
        return False
    return mfi.iloc[-1] < 20 or mfi.iloc[-1] > 80

# === Indikator Harga di Atas MA ===
def check_price_above_ma(data, ma_period):
    if len(data) < ma_period:
        return False
    ma = data['Close'].rolling(window=ma_period).mean()
    last_ma = ma.iloc[-1]
    last_close = data['Close'].iloc[-1]
    if pd.isna(last_ma):
        return False
    return last_close > last_ma

# === Aplikasi Streamlit ===
def main():
    st.set_page_config(page_title="Analisa Saham: RSI + MFI + MA", layout="wide")
    st.sidebar.header("⚙️ Pengaturan Analisis")

    sheet_url = st.sidebar.text_input("URL Google Sheets", value="https://docs.google.com/spreadsheets/d/1t6wgBIcPEUWMq40GdIH1GtZ8dvI9PZ2v/edit?usp=sharing")
    end_analysis_date = st.sidebar.date_input("Tanggal Akhir Analisis", value=datetime.today())

    st.sidebar.header("📌 Pilih Indikator")
    rsi_check = st.sidebar.checkbox("RSI Bullish Divergence")
    mfi_check = st.sidebar.checkbox("MFI Oversold (<20) atau Overbought (>80)")
    ma_check = st.sidebar.checkbox("Harga di atas MA")
    ma_period = st.sidebar.selectbox("Pilih MA:", options=[5, 10, 20], index=0, disabled=not ma_check)

    run = st.sidebar.button("🚀 Jalankan Analisa")

    st.title("📊 Analisa Saham: RSI + MFI + MA")

    if run:
        if not (rsi_check or mfi_check or ma_check):
            st.warning("⚠️ Pilih minimal satu indikator untuk memulai analisa.")
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
            if data is None or len(data) < 20:
                progress_bar.progress((i + 1) / len(tickers))
                continue

            match = []
            if rsi_check and detect_rsi_bullish_divergence(data):
                match.append("RSI Bullish Divergence")
            if mfi_check and detect_mfi_signal(data):
                match.append("MFI Oversold/Overbought")
            if ma_check and check_price_above_ma(data, ma_period):
                match.append(f"Price > MA{ma_period}")

            if len(match) == sum([rsi_check, mfi_check, ma_check]):
                results.append({
                    "Ticker": ticker,
                    "Last Close": round(data['Close'].iloc[-1], 2),
                    "Indikator Terpenuhi": ", ".join(match)
                })

            progress_bar.progress((i + 1) / len(tickers))

        st.subheader("📈 Hasil Analisis Saham")
        if results:
            st.success("✅ Saham yang memenuhi kriteria:")
            st.dataframe(pd.DataFrame(results))
        else:
            st.warning("❌ Tidak ada saham yang memenuhi kombinasi indikator.")

        # Contoh Saham BBCA
        st.subheader("📊 Contoh Data Saham BBCA")
        bbca_data = get_stock_data("BBCA", end_analysis_date)
        if bbca_data is not None:
            st.dataframe(bbca_data.tail(50))
        else:
            st.error("Gagal mengambil data BBCA.")

if __name__ == "__main__":
    main()
