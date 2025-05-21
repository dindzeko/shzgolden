import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta
import re

# ================== Fungsi Utilitas ==================
def extract_google_sheet_id(url):
    """Ekstrak ID Google Sheet dari berbagai format URL"""
    patterns = [
        r"/d/([a-zA-Z0-9-_]+)",
        r"id=([a-zA-Z0-9-_]+)",
        r"/([a-zA-Z0-9-_]{44})/"
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def load_google_sheet(sheet_url):
    """Membaca data dari Google Sheets dengan validasi"""
    try:
        file_id = extract_google_sheet_id(sheet_url)
        if not file_id:
            st.error("Format URL Google Sheets tidak valid")
            return None
            
        export_url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv"
        df = pd.read_csv(export_url)
        
        if 'Ticker' not in df.columns:
            st.error("Kolom 'Ticker' tidak ditemukan di sheet")
            return None
            
        return df.dropna(subset=['Ticker'])
    except Exception as e:
        st.error(f"Gagal membaca Google Sheet: {str(e)}")
        return None

def get_stock_data(ticker, end_date):
    """Mengambil data historis saham dengan error handling"""
    try:
        start_date = end_date - timedelta(days=100)  # Buffer untuk data cukup
        stock = yf.Ticker(f"{ticker}.JK")
        data = stock.history(
            start=start_date.strftime('%Y-%m-%d'),
            end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d')  # Inklusif end_date
        )
        return data.iloc[-50:] if len(data) >= 50 else None  # Pastikan 50 data terakhir
    except Exception as e:
        st.error(f"Gagal mengambil data {ticker}: {str(e)}")
        return None

# ================== Indikator Teknikal ==================
def calculate_rsi(data, window=14):
    """Menghitung RSI dengan EMA"""
    delta = data['Close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    avg_gain = gain.ewm(alpha=1/window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/window, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_adi(data):
    """Menghitung Accumulation/Distribution Index dengan handling division by zero"""
    high_low_range = data['High'] - data['Low']
    high_low_range = high_low_range.replace(0, np.nan)  # Hindari division by zero
    
    clv = ((data['Close'] - data['Low']) - (data['High'] - data['Close'])) / high_low_range
    clv = clv.fillna(0)
    return (clv * data['Volume']).cumsum()

def detect_macd(data):
    """Menghitung MACD sekaligus untuk optimasi"""
    close = data['Close']
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal

def detect_volume_spike(data, threshold=2.0):
    """Deteksi volume spike (volume hari ini > threshold * rata-rata 5 hari sebelumnya)"""
    if len(data) < 6:
        return False
    recent_avg_vol = data['Volume'][-6:-1].mean()
    last_vol = data['Volume'].iloc[-1]
    return last_vol > threshold * recent_avg_vol

def detect_golden_cross(data):
    """Deteksi Golden Cross (MA50 crossing MA200 ke atas)"""
    if len(data) < 200:
        return False
    ma50 = data['Close'].rolling(window=50).mean()
    ma200 = data['Close'].rolling(window=200).mean()
    return (ma50.iloc[-2] < ma200.iloc[-2]) and (ma50.iloc[-1] > ma200.iloc[-1])

def detect_consolidation(data, bb_window=20, bb_std=2, adx_threshold=20):
    """Deteksi konsolidasi berdasarkan Bollinger Bands squeeze dan ADX rendah"""
    if len(data) < bb_window + 10:
        return False
    
    close = data['Close']
    ma = close.rolling(bb_window).mean()
    std = close.rolling(bb_window).std()
    upper_band = ma + bb_std * std
    lower_band = ma - bb_std * std
    band_width = upper_band - lower_band
    
    # Bollinger Bands squeeze: bandwidth paling kecil 3 hari terakhir
    squeeze = band_width.iloc[-3:].max() < band_width.iloc[-20:-3].mean()
    
    # Hitung ADX
    high = data['High']
    low = data['Low']
    close = data['Close']
    plus_dm = high.diff()
    minus_dm = low.diff().abs()
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    
    plus_di = 100 * plus_dm.rolling(14).mean() / atr
    minus_di = 100 * minus_dm.rolling(14).mean() / atr
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.rolling(14).mean()
    
    adx_low = adx.iloc[-3:].max() < adx_threshold
    
    return squeeze and adx_low

def detect_rsi_divergence(data, rsi):
    """Deteksi RSI Bullish Divergence sederhana"""
    if len(rsi) < 20:
        return False
    
    # Ambil subset 20 bar terakhir sebelum bar terakhir
    subset_rsi = rsi[-20:-1]
    subset_close = data['Close'][-20:-1]
    
    low_rsi_idx = subset_rsi.idxmin()   # index label (bisa datetime)
    low_price_idx = subset_close.idxmin()  # index label
    
    last_rsi = rsi.iloc[-1]
    last_price = data['Close'].iloc[-1]
    
    # Gunakan .loc untuk akses berdasarkan index label
    if last_rsi > rsi.loc[low_rsi_idx] and last_price < data['Close'].loc[low_price_idx]:
        return True
    return False

# ================== Logika Deteksi ==================
def detect_indicators(data):
    """Mendeteksi semua indikator sekaligus untuk optimasi"""
    if data is None or len(data) < 50:
        return {}
    
    macd, signal = detect_macd(data)
    rsi = calculate_rsi(data)
    adi = calculate_adi(data)
    
    return {
        'RSI Oversold': rsi.iloc[-1] < 30,
        'RSI Exit Oversold': rsi.iloc[-2] < 30 and rsi.iloc[-1] > 30,
        'RSI Bullish Divergence': detect_rsi_divergence(data, rsi),
        'MACD Bullish': macd.iloc[-2] < signal.iloc[-2] and macd.iloc[-1] > signal.iloc[-1],
        'MACD Strong Bullish': macd.iloc[-1] > 0 and (macd.iloc[-1] > signal.iloc[-1]),
        'Volume Melejit': detect_volume_spike(data),
        'Golden Cross': detect_golden_cross(data),
        'Akumulasi': adi.iloc[-1] > adi.iloc[-5],
        'Distribusi': adi.iloc[-1] < adi.iloc[-5],
        'Konsolidasi': detect_consolidation(data)
    }

# ================== UI & Kontrol ==================
def main():
    st.set_page_config(page_title="Screener Saham ID", layout="wide")
    
    with st.sidebar:
        st.header("⚙️ Konfigurasi")
        sheet_url = st.text_input(
            "URL Google Sheets",
            value="https://docs.google.com/spreadsheets/d/1t6wgBIcPEUWMq40GdIH1GtZ8dvI9PZ2v/edit?gid=1445483445#gid=1445483445",
            help="Contoh: https://docs.google.com/spreadsheets/d/1abc.../edit"
        )
        end_date = st.date_input("Tanggal Akhir", datetime.today())
        
        st.header("📈 Filter Indikator")
        indicator_options = {
            'RSI Oversold': True,
            'MACD Bullish': True,
            'Volume Melejit': True,
            'Konsolidasi': True
        }
        selected_indicators = [k for k,v in indicator_options.items() if st.checkbox(k, value=v)]
        
        mode = st.radio("Mode Screening", [
            'Semua Indikator Terpenuhi',
            'Minimal 3 Indikator',
            'Custom Threshold'
        ])
    
    if st.button("🚀 Jalankan Screening"):
        df = load_google_sheet(sheet_url)
        if df is None:
            return
            
        tickers = df['Ticker'].unique()
        results = []
        
        with st.spinner(f"Memproses {len(tickers)} saham..."):
            for ticker in tickers:
                data = get_stock_data(ticker, end_date)
                if data is None:
                    continue
                
                detected = detect_indicators(data)
                matched = [k for k,v in detected.items() if v]
                
                # Logika seleksi
                if mode == 'Semua Indikator Terpenuhi':
                    if not all(ind in matched for ind in selected_indicators):
                        continue
                elif mode == 'Minimal 3 Indikator':
                    if len(set(matched) & set(selected_indicators)) < 3:
                        continue
                
                results.append({
                    'Ticker': ticker,
                    'Harga Terakhir': round(data['Close'].iloc[-1], 2),
                    'Indikator': ', '.join(matched),
                    'Vol (Jt)': f"{data['Volume'].iloc[-1]/1e6:.1f}M"
                })
        
        if results:
            result_df = pd.DataFrame(results)
            st.success(f"🔍 Ditemukan {len(results)} saham:")
            st.dataframe(
                result_df.sort_values('Harga Terakhir', ascending=False),
                use_container_width=True
            )
        else:
            st.warning("Tidak ada saham yang memenuhi kriteria")

if __name__ == "__main__":
    main()
