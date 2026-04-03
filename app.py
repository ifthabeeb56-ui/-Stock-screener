import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

# --- 1. പേജ് സെറ്റപ്പ് ---
st.set_page_config(page_title="HRC Pro Analyzer V6.7", layout="wide")

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

# --- 4. മെയിൻ അനാലിസിസ് ലോജിക് ---
def analyze_stock(ticker, f_p, s_p, rsi_min, use_ema, use_rsi, use_vol, use_adx, smart_on):
    try:
        symbol = str(ticker).strip().upper()
        df = yf.download(symbol + ".NS", period="1y", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < s_p: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        close, high, low = df['Close'].astype(float), df['High'].astype(float), df['Low'].astype(float)
        
        # ADX Logic
        plus_dm = high.diff().clip(lower=0)
        minus_dm = low.diff().clip(upper=0).abs()
        tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean()
        plus_di = 100 * (plus_dm.rolling(window=14).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=14).mean() / atr)
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        adx = dx.rolling(window=14).mean().iloc[-1]

        # EMA & RSI Logic
        ema_f, ema_s = close.ewm(span=f_p, adjust=False).mean(), close.ewm(span=s_p, adjust=False).mean()
        delta = close.diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-1 * delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rsi = 100 - (100 / (1 + (gain / loss.replace(0, np.nan))))
        
        curr_p = float(close.iloc[-1])
        c_rsi = float(rsi.iloc[-1])
        avg_vol = float(df['Volume'].iloc[-14:-1].mean())
        vol_ok = (float(df['Volume'].iloc[-1]) / avg_vol > 1.5) if use_vol and avg_vol > 0 else True
        recent_high = float(df['High'].iloc[-14:-1].max())

        ema_ok = (curr_p > ema_f.iloc[-1] and ema_f.iloc[-1] > ema_s.iloc[-1]) if use_ema else True
        rsi_ok = (c_rsi > rsi_min) if use_rsi else True
        adx_ok = (adx > 25) if use_adx else True

        signal = "⏳ WAIT"
        if ema_ok and rsi_ok and vol_ok and adx_ok:
            signal = "🚀 SMART" if (smart_on and curr_p > recent_high) else "✅ BUY"
        elif use_ema and curr_p < ema_s.iloc[-1]: 
            signal = "⚠️ EXIT"

        t_count, win_r, avg_p = perform_backtest(df, f_p, s_p, rsi_min)
        return {"Ticker": symbol, "Price": int(curr_p), "Signal": signal, "RSI": int(c_rsi), "Win%": int(win_r), "Avg%": avg_p}
    except:
        return None

# --- 5. കൗഫ്മാൻ ചാനൽ ലോജിക് ---
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
        
        return {"Ticker": symbol, "Price": int(curr_p), "Signal": signal, "Slope": round(slope, 2)}
    except: return None

# --- 6. മെയിൻ ഇന്റർഫേസ് ---
def main():
    st.title("📈 HRC Pro Analyzer V6.7")
    
    st.sidebar.header("⚙️ General Settings")
    f_n = st.sidebar.number_input("Fast EMA", value=50)
    s_n = st.sidebar.number_input("Slow EMA", value=200)
    rsi_val = st.sidebar.slider("Min RSI Limit", 20, 80, 50)
    
    st.sidebar.subheader("Filters")
    t_ema = st.sidebar.checkbox("EMA Filter", True)
    t_rsi = st.sidebar.checkbox("RSI Filter", True)
    t_vol = st.sidebar.checkbox("Volume Filter", True)
    t_adx = st.sidebar.checkbox("ADX Filter", True)
    t_smart = st.sidebar.checkbox("SMART Mode", True)

    tab1, tab2, tab3 = st.tabs(["🔍 Market Scan", "🌊 Channel Strategy", "💰 Portfolio"])
    
    with tab1:
        idx = st.selectbox("Select Index:", ["Nifty 50", "Nifty Next 50", "Nifty 100", "Nifty 500"])
        if st.button(f"Scan {idx}", use_container_width=True):
            run_general_scanner(get_index_stocks(idx), f_n, s_n, rsi_val, t_ema, t_rsi, t_vol, t_adx, t_smart)

    with tab2:
        idx_ch = st.selectbox("Select Index for Channel Scan:", ["Nifty 50", "Nifty Next 50", "Nifty 100", "Nifty 500"], key="ch_idx")
        lookback = st.slider("Channel Period", 10, 100, 40)
        if st.button("Start Channel Scan", use_container_width=True):
            run_channel_scanner(get_index_stocks(idx_ch), lookback)

    with tab3:
        p_in = st.text_area("Symbols (SBIN, RELIANCE...):", height=80)
        combined = list(set([s.strip().upper() for s in p_in.split(",") if s.strip()] + st.session_state.watchlist))
        if st.button("Analyze Portfolio", use_container_width=True):
            run_general_scanner(combined, f_n, s_n, rsi_val, t_ema, t_rsi, t_vol, t_adx, t_smart)

def run_general_scanner(stocks, f_n, s_n, rsi_val, t_ema, t_rsi, t_vol, t_adx, t_smart):
    results = []
    bar = st.progress(0)
    for i, t in enumerate(stocks):
        res = analyze_stock(t, f_n, s_n, rsi_val, t_ema, t_rsi, t_vol, t_adx, t_smart)
        if res: results.append(res)
        bar.progress((i + 1) / len(stocks))
    if results:
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else: st.warning("No data found.")

def run_channel_scanner(stocks, lookback):
    results = []
    bar = st.progress(0)
    for i, t in enumerate(stocks):
        res = analyze_channel(t, lookback)
        if res: results.append(res)
        bar.progress((i + 1) / len(stocks))
    if results:
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True)
    else: st.warning("No data found.")

if __name__ == "__main__":
    main()
