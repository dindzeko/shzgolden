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
    return 100 - (100 / (1 + rs))

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

# ================== Logika Deteksi ==================
def detect_rsi_divergence(data, rsi):
    """Deteksi RSI Bullish Divergence sederhana (contoh)"""
    # Implementasi sederhana untuk ilustrasi, bisa dikembangkan lebih lanjut
    if len(rsi) < 20:
        return False
    # Cek titik terendah RSI terakhir dan sebelumnya dengan harga
    low_rsi_idx = rsi[-20:-1].idxmin()
    low_price_idx = data['Close'][-20:-1].idxmin()
    last_rsi = rsi.iloc[-1]
    last_price = data['Close'].iloc[-1]
    # RSI naik tapi harga turun = divergence bullish
    if last_rsi > rsi.iloc[low_rsi_idx] and last_price < data['Close'].iloc[low_price_idx]:
        return True
    return False

def detect_volume_spike(data, factor=2):
    """Deteksi volume spike: volume hari terakhir > factor x rata-rata volume 10 hari sebelumnya"""
    if len(data) < 11:
        return False
    recent_vol = data['Volume'].iloc[-1]
    avg_vol = data['Volume'].iloc[-11:-1].mean()
    return recent_vol > factor * avg_vol

def detect_golden_cross(data):
    """Deteksi Golden Cross: MA50 crossing MA200 dari bawah ke atas"""
    if len(data) < 200:
        return False
    ma50 = data['Close'].rolling(window=50).mean()
    ma200 = data['Close'].rolling(window=200).mean()
    # Cek crossing hari terakhir dan sebelumnya
    cross_today = ma50.iloc[-1] > ma200.iloc[-1]
    cross_yesterday = ma50.iloc[-2] <= ma200.iloc[-2]
    return cross_today and cross_yesterday

def detect_consolidation(data, window=20, threshold=0.02):
    """Deteksi konsolidasi: range harga kecil dalam periode tertentu"""
    if len(data) < window:
        return False
    recent = data['Close'].iloc[-window:]
    max_close = recent.max()
    min_close = recent.min()
    return (max_close - min_close) / min_close < threshold

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
