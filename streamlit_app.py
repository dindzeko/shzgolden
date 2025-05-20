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
def get_stock_data(ticker, end_date):
    try:
        stock = yf.Ticker(f"{ticker}.JK")
        start_date = end_date - timedelta(days=60)  # Ambil 60 hari untuk indikator teknikal
        data = stock.history(start=start_date.strftime('%Y-%m-%d'),
                             end=end_date.strftime('%Y-%m-%d'))
        if len(data) < 30:
            return None
        return data
    except Exception as e:
        # st.warning(f"Error fetching data for {ticker}: {str(e)}")
        return None

# 1. Golden Cross: MA20 > MA50 (baru saja crossover)
def detect_golden_cross(data):
    if len(data) < 50:
        return False
    data = data.copy()
    data['MA20'] = data['Close'].rolling(20).mean()
    data['MA50'] = data['Close'].rolling(50).mean()
    return data['MA20'].iloc[-2] < data['MA50'].iloc[-2] and data['MA20'].iloc[-1] > data['MA50'].iloc[-1]

# 2. RSI Oversold: RSI < 30
def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def detect_rsi_oversold(data):
    rsi = calculate_rsi(data)
    return len(rsi) > 0 and rsi.iloc[-1] < 30

# 3. MACD Bullish Crossover
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

# 4. Volume naik 2 hari berturut-turut
def detect_volume_up_two_days(data):
    if len(data) < 2:
        return False
    return data['Volume'].iloc[-1] > data['Volume'].iloc[-2]

# === MAIN FUNCTION ===
def main():
    st.title("🔍 Saham Potensial Beli - Screening Otomatis")

    st.markdown("""
    ### Kriteria Screening:
    - **Wajib**:  
      - RSI Oversold (<30): Harga oversold, potensi rebound  
      - MACD Bullish Crossover: Momentum naik  
      - Volume Naik 2 Hari Berturut-turut  
    - **Opsional**:  
      - Golden Cross (bisa diaktifkan/menonaktifkan via checkbox di bawah)
    """)

    # Input URL Google Drive
    file_url = st.text_input(
        "Masukkan URL Google Sheets",
        value="https://docs.google.com/spreadsheets/d/1t6wgBIcPEUWMq40GdIH1GtZ8dvI9PZ2v/edit?usp=drive_link&ouid=106044501644618784207&rtpof=true&sd=true "
    )

    analysis_date = st.date_input("Tanggal Analisis", value=datetime.today())

    # Checkbox untuk Golden Cross
    use_golden_cross = st.checkbox("Aktifkan Filter Golden Cross", value=True)

    if st.button("Mulai Screening"):
        df = load_google_drive_excel(file_url)
        if df is None or 'Ticker' not in df.columns:
            st.error("File Excel tidak valid atau tidak memiliki kolom 'Ticker'")
            return

        tickers = df['Ticker'].tolist()
        total_tickers = len(tickers)
        st.info(f"Jumlah total ticker yang akan dianalisa: {total_tickers}")

        progress_bar = st.progress(0)
        status_text = st.empty()  # Placeholder untuk teks status

        matches = []

        for idx, ticker in enumerate(tickers):
            data = get_stock_data(ticker, analysis_date)

            if data is None:
                # Lanjutkan tanpa tambah error
                pass
            else:
                criteria_met = []
                criteria_required = ["RSI Oversold", "MACD Bullish", "Volume Naik 2 Hari"]

                if use_golden_cross and detect_golden_cross(data):
                    criteria_met.append("Golden Cross")
                if detect_rsi_oversold(data):
                    criteria_met.append("RSI Oversold")
                if detect_macd_bullish_crossover(data):
                    criteria_met.append("MACD Bullish")
                if detect_volume_up_two_days(data):
                    criteria_met.append("Volume Naik 2 Hari")

                # Jika semua kriteria wajib terpenuhi
                if all(req in criteria_met for req in criteria_required):
                    if use_golden_cross:
                        if "Golden Cross" in criteria_met:
                            matches.append({
                                "Ticker": ticker,
                                "Harga Terakhir": round(data['Close'].iloc[-1], 2),
                                "Kriteria Terpenuhi": ", ".join(criteria_met)
                            })
                    else:
                        matches.append({
                            "Ticker": ticker,
                            "Harga Terakhir": round(data['Close'].iloc[-1], 2),
                            "Kriteria Terpenuhi": ", ".join(criteria_met)
                        })

            # Update progress bar dan status text
            progress = (idx + 1) / total_tickers
            progress_bar.progress(progress)
            status_text.text(f"Memproses saham ke-{idx + 1} dari {total_tickers}...")

        # Tampilkan hasil akhir
        if matches:
            st.success(f"✅ Hasil Screening ({len(matches)} Saham Ditemukan):")
            result_df = pd.DataFrame(matches)
            st.dataframe(result_df)
        else:
            st.info("❌ Tidak ada saham yang memenuhi kriteria.")

if __name__ == "__main__":
    main()
