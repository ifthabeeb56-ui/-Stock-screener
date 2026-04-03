import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

# --- 1. പേജ് സെറ്റപ്പ് ---
st.set_page_config(page_title="HRC Pro Analyzer V6", layout="wide")

if 'watchlist' not in st.session_state:
    st.session_state.watchlist = []

# --- 2. ഇൻഡക്സ് ഡാറ്റ ---
@st.cache_data(ttl=86400)
def get_index_stocks(index_name):
    indices = {
        "Nifty 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        "Nifty Next 50": "https://archives.nseindia.com/content/indices/ind_niftynext50list.csv",
        "Nifty 100": "https://archives.nseindia.com/content/indices/ind_nifty100list.csv",
        "Nifty 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv",
        "Nifty Bank": "https://archives.nseindia.com/content/indices/ind_niftybanklist.csv",
        "Nifty IT": "https://archives.nseindia.com/content/indices/ind_niftyitlist.csv"
    }
    try:
        url = indices.get(index_name)
        df = pd.read_csv(url)
        col = 'Symbol' if 'Symbol' in df.columns else df.columns[0]
        return df[col].str.strip().tolist()
    except:
        return ["RELIANCE", "TCS", "HDFCBANK", "INFY"]

# --- 3. ബാക്ക്-ടെസ്റ്റ് ലോജിക് ---
def perform_backtest(df, f_p, s_p, rsi_min):
    try:
        close = df['Close'].astype(float)
        ema_f = close.ewm(span=f_p, adjust=False).mean()
        ema_s = close.ewm(span=s_p, adjust=False).mean()
        
        delta = close.diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-1 * delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rsi = 100 - (100 / (1 + (gain / loss.replace(0, np.nan))))
        
        trades = []
        in_pos, buy_p = False, 0
        
        for i in range(s_p, len(df)):
            curr_p = float(close.iloc[i])
            if not in_pos:
                if curr_p > ema_f.iloc[i] and ema_f.iloc[i] > ema_s.iloc[i] and rsi.iloc[i] > rsi_min:
                    in_pos, buy_p = True, curr_p
            elif in_pos:
                if curr_p < ema_s.iloc[i]:
                    trades.append(((curr_p - buy_p) / buy_p) * 100)
                    in_pos = False
                    
        if trades:
            win_r = (len([t for t in trades if t > 0]) / len(trades)) * 100
            return len(trades), round(win_r, 0), round(sum(trades)/len(trades), 1)
        return 0, 0, 0
    except: return 0, 0, 0

# --- 4. അനാലിസിസ് ലോജിക് (ADX & 14 Day Vol/High) ---
def analyze_stock(ticker, f_p, s_p, rsi_min, use_ema, use_rsi, use_vol, smart_on):
    try:
        symbol = str(ticker).strip().upper()
        df = yf.download(symbol + ".NS", period="1y", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < s_p: return None
        
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        close, high, low = df['Close'].astype(float), df['High'].astype(float), df['Low'].astype(float)
        
        # ADX Calculation (Trend Strength)
        plus_dm = high.diff().clip(lower=0)
        minus_dm = low.diff().clip(upper=0).abs()
        tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean()
        plus_di = 100 * (plus_dm.rolling(window=14).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=14).mean() / atr)
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
