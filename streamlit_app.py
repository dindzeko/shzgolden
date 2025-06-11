import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import numpy as np

# === Improved Data Loading with Caching ===
@st.cache_data(ttl=3600, show_spinner=False)
def load_google_sheet(sheet_url):
    """Load data from Google Sheets with better error handling and caching"""
    try:
        file_id = sheet_url.split("/d/")[1].split("/")[0]
        export_url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv"
        df = pd.read_csv(export_url)
        
        # Normalize column names
        df.columns = df.columns.str.strip().str.title()
        
        if 'Ticker' not in df.columns:
            st.error("Kolom 'Ticker' tidak ditemukan di Google Sheets.")
            return None
        return df
    except Exception as e:
        st.error(f"Gagal membaca Google Sheet: {str(e)}")
        return None

# === Efficient Stock Data Fetching with Caching ===
@st.cache_data(ttl=3600, show_spinner=False)
def get_stock_data(ticker, end_date, days_back=90):
    """Get stock data with caching and error handling"""
    try:
        start_date = end_date - timedelta(days=days_back)
        stock = yf.Ticker(f"{ticker}.JK")
        data = stock.history(
            start=start_date.strftime('%Y-%m-%d'),
            end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d')  # Include end date
        )
        return data if not data.empty else None
    except Exception as e:
        st.error(f"Error mendapatkan data {ticker}: {str(e)}")
        return None

# === Technical Indicators ===
def calculate_rsi(data, window=14):
    """Calculate RSI with vectorized operations"""
    delta = data['Close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.rolling(window).mean()
    avg_loss = loss.rolling(window).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)  # Neutral value for NaN

def detect_rsi_bullish_divergence(data):
    """Improved RSI divergence detection with lookback window"""
    if len(data) < 30:
        return False
    
    rsi = calculate_rsi(data)
    close = data['Close']
    
    # Find lowest lows in last 30 days
    low_idx = close.rolling(15).apply(lambda x: x.idxmin(), raw=False).dropna()
    
    if len(low_idx) < 2:
        return False
    
    # Get two most recent lows
    low1_idx = low_idx.iloc[-2]
    low2_idx = low_idx.iloc[-1]
    
    # Validate divergence pattern
    price_lower = close[low2_idx] < close[low1_idx]
    rsi_higher = rsi[low2_idx] > rsi[low1_idx]
    
    return price_lower and rsi_higher

def calculate_mfi(data, window=14):
    """Vectorized MFI calculation"""
    tp = (data['High'] + data['Low'] + data['Close']) / 3
    rmf = tp * data['Volume']
    
    # Get money flow direction
    mf_direction = np.where(tp > tp.shift(1), 1, np.where(tp < tp.shift(1), -1, 0))
    
    # Calculate positive/negative money flow
    pos_mf = np.where(mf_direction == 1, rmf, 0)
    neg_mf = np.where(mf_direction == -1, rmf, 0)
    
    # Rolling sums
    pos_mf_sum = pd.Series(pos_mf).rolling(window).sum()
    neg_mf_sum = pd.Series(neg_mf).rolling(window).sum()
    
    # Calculate MFI
    mfi = 100 * pos_mf_sum / (pos_mf_sum + neg_mf_sum)
    return mfi

def detect_mfi_signal(data):
    """MFI signal detection with bounds checking"""
    mfi = calculate_mfi(data)
    if len(mfi) < 1 or mfi.iloc[-1] is np.nan:
        return False
    return mfi.iloc[-1] < 20 or mfi.iloc[-1] > 80

def check_price_above_ma(data, ma_period):
    """Check price position relative to MA"""
    if len(data) < ma_period:
        return False
        
    ma = data['Close'].rolling(ma_period).mean()
    last_close = data['Close'].iloc[-1]
    last_ma = ma.iloc[-1]
    
    return not np.isnan(last_ma) and last_close > last_ma

# === Streamlit App ===
def main():
    st.set_page_config(
        page_title="Analisa Saham: RSI + MFI + MA", 
        layout="wide",
        page_icon="📈"
    )
    
    # Sidebar Configuration
    st.sidebar.header("⚙️ Pengaturan Analisis")
    sheet_url = st.sidebar.text_input(
        "URL Google Sheets",
        value="https://docs.google.com/spreadsheets/d/1t6wgBIcPEUWMq40GdIH1GtZ8dvI9PZ2v/edit?usp=sharing"
    )
    end_analysis_date = st.sidebar.date_input(
        "Tanggal Akhir Analisis", 
        value=datetime.today()
    )
    
    st.sidebar.header("📌 Pilih Indikator")
    rsi_check = st.sidebar.checkbox("RSI Bullish Divergence", True)
    mfi_check = st.sidebar.checkbox("MFI Oversold (<20) atau Overbought (>80)", True)
    ma_check = st.sidebar.checkbox("Harga di atas MA", True)
    ma_period = st.sidebar.selectbox(
        "Pilih MA:", 
        options=[5, 10, 20], 
        index=0,
        disabled=not ma_check
    )
    
    st.sidebar.markdown("---")
    st.sidebar.info("✅ Pilih indikator yang ingin digunakan untuk analisis")
    
    # Main Content
    st.title("📊 Analisa Saham: RSI + MFI + MA")
    st.markdown("""
    Aplikasi ini menganalisis saham berdasarkan:
    - **RSI Bullish Divergence**: Harga membuat lower low tapi RSI membuat higher low
    - **MFI**: Money Flow Index menunjukkan kondisi oversold (<20) atau overbought (>80)
    - **Moving Average**: Harga penutupan di atas moving average
    """)
    
    if st.button("🚀 Jalankan Analisa", key="run_analysis"):
        # Validation
        if not (rsi_check or mfi_check or ma_check):
            st.warning("⚠️ Pilih minimal satu indikator untuk memulai analisa.")
            return
            
        # Load data
        df = load_google_sheet(sheet_url)
        if df is None or df.empty:
            return
            
        tickers = df['Ticker'].dropna().unique().tolist()
        st.info(f"🔍 Menganalisis {len(tickers)} saham...")
        
        # Analysis
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, ticker in enumerate(tickers):
            status_text.text(f"Memproses {ticker} ({i+1}/{len(tickers)})")
            data = get_stock_data(ticker, end_analysis_date)
            
            if data is None or len(data) < 30:
                progress_bar.progress((i + 1) / len(tickers))
                continue
                
            conditions = []
            if rsi_check:
                conditions.append(detect_rsi_bullish_divergence(data))
            if mfi_check:
                conditions.append(detect_mfi_signal(data))
            if ma_check:
                conditions.append(check_price_above_ma(data, ma_period))
                
            # Check if all selected conditions are met
            if all(conditions):
                results.append({
                    "Ticker": ticker,
                    "Last Close": round(data['Close'].iloc[-1], 2),
                    "Volume": f"{data['Volume'].iloc[-1]:,}",
                    "Indikator Terpenuhi": " | ".join([
                        "RSI Divergence" if rsi_check and conditions[0] else "",
                        "MFI Signal" if mfi_check and conditions[len(conditions)-2] else "",
                        f"MA{ma_period}" if ma_check and conditions[-1] else ""
                    ]).strip(" |")
                })
                
            progress_bar.progress((i + 1) / len(tickers))
        
        # Display results
        st.subheader("📈 Hasil Analisis Saham")
        if results:
            result_df = pd.DataFrame(results)
            st.success(f"✅ Ditemukan {len(result_df)} saham yang memenuhi kriteria:")
            st.dataframe(result_df.sort_values("Last Close", ascending=False))
            
            # Show chart example
            st.subheader(f"📊 Contoh Grafik {results[0]['Ticker']}")
            sample_data = get_stock_data(results[0]['Ticker'], end_analysis_date)
            if sample_data is not None:
                st.line_chart(sample_data[['Close', 'Volume']], use_container_width=True)
        else:
            st.warning("❌ Tidak ada saham yang memenuhi kombinasi indikator.")
            
        progress_bar.empty()
        status_text.empty()

if __name__ == "__main__":
    main()
