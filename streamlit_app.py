import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# === Fungsi Membaca Google Sheets ===
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

# === Fungsi Mengambil Data Saham ===
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

# === Indikator Money Flow Index (MFI) ===
def calculate_mfi(data, period=14):
    typical_price = (data['High'] + data['Low'] + data['Close']) / 3
    raw_money_flow = typical_price * data['Volume']
    direction = typical_price.diff()
    positive_flow = raw_money_flow.where(direction > 0, 0)
    negative_flow = raw_money_flow.where(direction < 0, 0)
    pos_mf = positive_flow.rolling(period).sum()
    neg_mf = negative_flow.rolling(period).sum()
    mfi = 100 - (100 / (1 + (pos_mf / neg_mf)))
    return mfi

# === Fungsi MA ===
def calculate_ma_condition(data, ma_period):
    if len(data) < ma_period:
        return False, None
    ma = data['Close'].rolling(window=ma_period).mean()
    ma_value = ma.iloc[-1]
    last_close = data['Close'].iloc[-1]
    return last_close > ma_value, round(ma_value, 2)

# === Aplikasi Utama ===
def main():
    st.set_page_config(page_title="Analisa Saham", layout="wide")
    st.title("📊 Analisa Saham: RSI + MFI + MA")

    # Sidebar
    st.sidebar.header("⚙️ Pengaturan Analisis")
    sheet_url = st.sidebar.text_input("URL Google Sheets", value="https://docs.google.com/spreadsheets/d/1t6wgBIcPEUWMq40GdIH1GtZ8dvI9PZ2v/edit?usp=sharing")
    end_analysis_date = st.sidebar.date_input("Tanggal Akhir Analisis", value=datetime.today())

    st.sidebar.header("📌 Pilih Indikator")
    use_rsi = st.sidebar.checkbox("RSI Bullish Divergence", value=True)
    use_mfi = st.sidebar.checkbox("MFI Oversold (<20) atau Overbought (>80)", value=True)
    use_ma = st.sidebar.checkbox("Harga di atas MA", value=False)

    ma_period = None
    if use_ma:
        ma_period = st.sidebar.selectbox("Pilih MA:", options=[5, 10, 20], index=0)

    if st.sidebar.button("🚀 Jalankan Analisa"):
        if not use_rsi and not use_mfi and not use_ma:
            st.warning("Pilih minimal satu indikator.")
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

            indikator_terpenuhi = []

            # Cek RSI
            rsi_ok = detect_rsi_bullish_divergence(data) if use_rsi else True
            if use_rsi and rsi_ok:
                indikator_terpenuhi.append("RSI Bullish Divergence")

            # Cek MFI
            mfi_ok = True
            mfi_ket = ""
            mfi_value = None
            if use_mfi:
                mfi_series = calculate_mfi(data)
                if not mfi_series.isna().all():
                    mfi_value = round(mfi_series.iloc[-1], 2)
                    if mfi_value < 20:
                        mfi_ket = "Oversold - potensi rebound"
                        indikator_terpenuhi.append("MFI Oversold")
                    elif mfi_value > 80:
                        mfi_ket = "Overbought - potensi koreksi"
                        indikator_terpenuhi.append("MFI Overbought")
                    else:
                        mfi_ok = False
                        mfi_ket = f"MFI Netral ({mfi_value})"
                else:
                    mfi_ok = False
                    mfi_ket = "MFI tidak tersedia"

            # Cek MA
            ma_ok = True
            ma_ket = ""
            ma_value = None
            if use_ma and ma_period:
                ma_ok, ma_value = calculate_ma_condition(data, ma_period)
                if ma_ok:
                    ma_ket = f"Close > MA{ma_period}"
                    indikator_terpenuhi.append(f"MA{ma_period} Terlewati")
                else:
                    ma_ket = f"Close < MA{ma_period}"

            # Simpan hasil jika semua indikator yang dicentang terpenuhi
            if rsi_ok and mfi_ok and ma_ok:
                results.append({
                    "Ticker": ticker,
                    "Last Close": round(data['Close'].iloc[-1], 2),
                    "Indikator Terpenuhi": ", ".join(indikator_terpenuhi),
                    "MFI": mfi_value,
                    "Ket. MFI": mfi_ket,
                    f"MA{ma_period}" if ma_period else "": ma_value,
                    "Ket. MA": ma_ket if use_ma else ""
                })

            progress_bar.progress((i + 1) / len(tickers))

        st.subheader("📈 Hasil Analisis Saham")
        if results:
            st.success(f"✅ Ditemukan {len(results)} saham yang memenuhi kriteria.")
            st.dataframe(pd.DataFrame(results))
        else:
            st.warning("❌ Tidak ada saham yang memenuhi kombinasi indikator.")

        # Tampilkan contoh data BBCA
        st.subheader("📊 Contoh Data Saham BBCA")
        bbca_data = get_stock_data("BBCA", end_analysis_date)
        if bbca_data is not None:
            st.dataframe(bbca_data.tail(50))
        else:
            st.error("Gagal mengambil data BBCA.")

if __name__ == "__main__":
    main()
