import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# Fungsi untuk membaca file Excel dari Google Drive
def load_google_drive_excel(file_url):
    try:
        file_id = file_url.split("/d/")[1].split("/")[0]
        download_url = f"https://drive.google.com/uc?export=download&id= {file_id}"
        df = pd.read_excel(download_url, engine='openpyxl')
        
        if 'Ticker' not in df.columns:
            st.error("The 'Ticker' column is missing in the Excel file.")
            return None
        
        st.success(f"Successfully loaded data from Google Drive!")
        st.info(f"Number of rows read: {len(df)}")
        st.info(f"Columns in the Excel file: {', '.join(df.columns)}")
        
        return df
    except Exception as e:
        st.error(f"Error loading Excel file from Google Drive: {e}")
        return None

# Fungsi untuk mengambil data saham
def get_stock_data(ticker, end_date):
    try:
        stock = yf.Ticker(f"{ticker}.JK")
        start_date = end_date - timedelta(days=180)  # Ambil 6 bulan data
        data = stock.history(start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
        
        if len(data) < 50:
            return None
        
        # Hitung Moving Average
        data['MA50'] = data['Close'].rolling(window=50).mean()
        data['MA100'] = data['Close'].rolling(window=100).mean()

        # Hitung RSI(14)
        delta = data['Close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        data['RSI'] = rsi

        return data.tail(2)  # Ambil 2 hari terakhir untuk deteksi crossing
    except Exception as e:
        st.warning(f"Error fetching data for {ticker}: {str(e)}")
        return None

# Fungsi mendeteksi Golden Cross dan ambil RSI + status
def detect_golden_cross_and_rsi(data):
    if len(data) >= 2:
        prev_ma50 = data.iloc[-2]['MA50']
        curr_ma50 = data.iloc[-1]['MA50']

        prev_ma100 = data.iloc[-2]['MA100']
        curr_ma100 = data.iloc[-1]['MA100']

        last_close = data.iloc[-1]['Close']
        last_rsi = data.iloc[-1]['RSI']

        # Deteksi Golden Cross
        golden_cross = (
            prev_ma50 <= prev_ma100 and
            curr_ma50 > curr_ma100 and
            curr_ma50 > last_close * 0.99  # Harga tidak jauh di bawah MA50
        )

        # Tentukan status RSI
        rsi_status = "Neutral"
        if pd.notna(last_rsi):
            if last_rsi > 70:
                rsi_status = "Overbought"
            elif last_rsi < 30:
                rsi_status = "Oversold"

        return golden_cross, last_rsi, rsi_status
    return False, None, "N/A"

# Main function
def main():
    st.title("Stock Screening - Golden Cross + RSI")

    file_url = "https://docs.google.com/spreadsheets/d/1t6wgBIcPEUWMq40GdIH1GtZ8dvI9PZ2v/edit?usp=drive_link&ouid=106044501644618784207&rtpof=true&sd=true "

    st.info("Loading data from Google Drive...")
    df = load_google_drive_excel(file_url)
    if df is None or 'Ticker' not in df.columns:
        st.error("Failed to load data or 'Ticker' column is missing.")
        return

    tickers = df['Ticker'].tolist()
    total_tickers = len(tickers)

    analysis_date = st.date_input("Analysis Date", value=datetime.today())

    if st.button("Analyze Stocks"):
        results = []
        progress_bar = st.progress(0)
        progress_text = st.empty()

        bbc_data = None

        for i, ticker in enumerate(tickers):
            data = get_stock_data(ticker, analysis_date)

            if ticker == "BBCA" and data is not None:
                bbc_data = data

            if data is not None and not data[['MA50', 'MA100']].isna().all().all():
                golden_cross, rsi_value, rsi_status = detect_golden_cross_and_rsi(data)

                if golden_cross:
                    results.append({
                        "Ticker": ticker,
                        "Last Close": round(data['Close'][-1], 2),
                        "Signal": "Golden Cross",
                        "RSI (14)": round(rsi_value, 2) if pd.notna(rsi_value) else "N/A",
                        "RSI Status": rsi_status
                    })

            progress = (i + 1) / total_tickers
            progress_bar.progress(progress)
            progress_text.text(f"Progress: {int(progress * 100)}%")

        if results:
            st.subheader("Results: Stocks with Golden Cross")
            results_df = pd.DataFrame(results)
            st.dataframe(results_df)
        else:
            st.info("No stocks match the Golden Cross pattern.")

        st.subheader("Separate Result for BBCA")
        if bbc_data is not None and not bbc_data.empty:
            st.write("Data Retrieved for BBCA:")
            st.dataframe(bbc_data[['Close', 'MA50', 'MA100', 'RSI']])
        else:
            st.warning("No data retrieved for BBCA.")

if __name__ == "__main__":
    main()
