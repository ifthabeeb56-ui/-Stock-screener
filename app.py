import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

# --- 1. പേജ് സെറ്റപ്പ് ---
st.set_page_config(page_title="HRC Pro Analyzer V6.5", layout="wide")

if 'watchlist' not in st.session_state:
    st.session_state.watchlist = []

# --- 2. ഇൻഡക്സ് ഡാറ്റ ---
@st.cache_data(ttl=86400)
def get_index_stocks(index_name):
    indices = {
        "Nifty 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        "Nifty Next 50": "https://archives.nseindia.com/content/indices/ind_niftynext50list.csv",
        "Nifty 100": "https://archives.nseindia.com/content/indices/ind_nifty100list.csv",
        "Nifty 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    }
    try:
        url = indices.get(index_name)
        df = pd.read_csv(url)
        col = 'Symbol' if 'Symbol' in df.columns else df.columns[0]
        return df[col].str.strip().tolist()
    except:
        return ["RELIANCE", "TCS", "HDFCBANK", "INFY"]

# --- 3. ചാനൽ സ്ട്രാറ്റജി ലോജിക് (Kaufman Logic) ---
def analyze_channel(ticker, period=40):
    try:
        symbol = str(ticker).strip().upper()
        df = yf.download(symbol + ".NS", period="1y", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < period: return None
        
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        close = df['Close'].astype(float)
        
        x = np.arange(period)
        y = close.iloc[-period:].values
        slope, intercept = np.polyfit(x, y, 1)
        linreg_val = slope * (period - 1) + intercept
        
        b, t = 0.0, 0.0
        for i in range(period):
            current_linreg = slope * i + intercept
            price_at_i = close.iloc[-(period-i)]
            b = max(b, current_linreg - price_at_i)
            t = max(t, price_at_i - current_linreg)
            
        upper_band = linreg_val + t + slope
        lower_band = linreg_val - b + slope
        curr_p = float(close.iloc[-1])
        
        signal = "⏳ WAIT"
        if curr_p > upper_band: signal = "🚀 CHANNEL BUY"
        elif curr_p < lower_band: signal = "⚠️ CHANNEL SELL"
        
        return {"Ticker": symbol, "Price": int(curr_p), "Signal": signal, "Slope": round(slope, 2), "Upper": int(upper_band), "Lower": int(lower_band)}
    except: return None

# --- 4. പഴയ സ്കാനർ ലോജിക് (EMA/RSI) ---
def analyze_stock(ticker, f_p, s_p, rsi_min, use_ema, use_rsi, use_vol, use_adx, smart_on):
    try:
        symbol = str(ticker).strip().upper()
        df = yf.download(symbol + ".NS", period="1y", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < s_p: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        close = df['Close'].astype(float)
        ema_f = close.ewm(span=f_p, adjust=False).mean()
        ema_s = close.ewm(span=s_p, adjust=False).mean()
        
        delta = close.diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-1 * delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rsi = 100 - (100 / (1 + (gain / loss.replace(0, np.nan))))
        
        curr_p, c_rsi = float(close.iloc[-1]), float(rsi.iloc[-1])
        ema_ok = (curr_p > ema_f.iloc[-1] and ema_f.iloc[-1] > ema_s.iloc[-1]) if use_ema else True
        rsi_ok = (c_rsi > rsi_min) if use_rsi else True
        
        signal = "⏳ WAIT"
        if ema_ok and rsi_ok: signal = "✅ BUY"
        elif use_ema and curr_p < ema_s.iloc[-1]: signal = "⚠️ EXIT"
        
        return {"Ticker": symbol, "Price": int(curr_p), "Signal": signal, "RSI": int(c_rsi)}
    except: return None

# --- 5. മെയിൻ ഇന്റർഫേസ് ---
def main():
    st.title("📈 HRC Pro Analyzer V6.5")
    
    tab1, tab2, tab3 = st.tabs(["🔍 Market Scan", "🌊 Channel Strategy", "💰 Portfolio"])
    
    with tab1:
        st.sidebar.header("⚙️ General Settings")
        f_n = st.sidebar.number_input("Fast EMA", value=50)
        s_n = st.sidebar.number_input("Slow EMA", value=200)
        rsi_val = st.sidebar.slider("Min RSI Limit", 20, 80, 50)
        
        idx = st.selectbox("Select Index:", ["Nifty 50", "Nifty Next 50", "Nifty 100", "Nifty 500"])
        if st.button(f"Scan {idx} (General)", use_container_width=True):
            stocks = get_index_stocks(idx)
            run_general_scanner(stocks, f_n, s_n, rsi_val)

    with tab2:
        st.subheader("Kaufman Channel Breakout Scan")
        idx_ch = st.selectbox("Select Index for Channel Scan:", ["Nifty 50", "Nifty Next 50", "Nifty 100", "Nifty 500"], key="ch_idx")
        lookback = st.slider("Channel Period", 10, 100, 40)
        if st.button("Start Channel Scan", use_container_width=True):
            stocks = get_index_stocks(idx_ch)
            run_channel_scanner(stocks, lookback)

    with tab3:
        st.subheader("Your Watchlist")
        if st.session_state.watchlist:
            st.write(st.session_state.watchlist)
        else:
            st.write("Watchlist is empty.")

# --- 6. സ്കാനർ ഫംഗ്ഷനുകൾ ---
def run_general_scanner(stocks, f_n, s_n, rsi_val):
    results = []
    bar = st.progress(0)
    for i, t in enumerate(stocks):
        res = analyze_stock(t, f_n, s_n, rsi_val, True, True, False, False, False)
        if res: results.append(res)
        bar.progress((i + 1) / len(stocks))
    if results:
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True)
        st.download_button("📥 Download Report", df.to_csv(index=False).encode('utf-8'), "general_scan.csv")

def run_channel_scanner(stocks, lookback):
    results = []
    bar = st.progress(0)
    for i, t in enumerate(stocks):
        res = analyze_channel(t, lookback)
        if res: results.append(res)
        bar.progress((i + 1) / len(stocks))
    
    if results:
        df = pd.DataFrame(results)
        c1, c2 = st.columns(2)
        with c1:
            st.success("### 🚀 CHANNEL BUY")
            d_buy = df[df['Signal'] == "🚀 CHANNEL BUY"]
            st.dataframe(d_buy)
            if not d_buy.empty: st.download_button("📥 Download Buy List", d_buy.to_csv(index=False).encode('utf-8'), "ch_buy.csv")
        with c2:
            st.error("### ⚠️ CHANNEL SELL")
            d_sell = df[df['Signal'] == "⚠️ CHANNEL SELL"]
            st.dataframe(d_sell)
            if not d_sell.empty: st.download_button("📥 Download Sell List", d_sell.to_csv(index=False).encode('utf-8'), "ch_sell.csv")
    else:
        st.warning("No data found.")

if __name__ == "__main__":
    main()
