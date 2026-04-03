import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import date

# --- 1. പേജ് സെറ്റപ്പ് ---
st.set_page_config(page_title="HRC Pro Analyzer V5", layout="wide")

# --- 2. ഇൻഡക്സ് ഡാറ്റ ലോഡിംഗ് ---
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
        # URL ലഭ്യമല്ലെങ്കിൽ ബാക്കപ്പ് ലിസ്റ്റ്
        return ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "AXISBANK", "SBIN"]

# --- 3. അനാലിസിസ് ലോജിക് ---
def analyze_stock(ticker, f_p, s_p, rsi_min, use_ema, use_rsi, use_vol, smart_on):
    try:
        yf_ticker = str(ticker).strip().upper() + ".NS"
        # 1 വർഷത്തെ ഡാറ്റ എടുക്കുന്നു
        df = yf.download(yf_ticker, period="1y", interval="1d", progress=False, auto_adjust=True)
        
        if df.empty or len(df) < s_p: 
            return None
        
        # MultiIndex കോളങ്ങൾ ഉണ്ടെങ്കിൽ മാറ്റുന്നു
        if isinstance(df.columns, pd.MultiIndex): 
            df.columns = df.columns.get_level_values(0)
        
        close = df['Close'].astype(float)
        
        # EMA കണക്കാക്കുന്നു
        ema_f = close.ewm(span=f_p, adjust=False).mean()
        ema_s = close.ewm(span=s_p, adjust=False).mean()
        
        # RSI കണക്കാക്കുന്നു
        delta = close.diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-1 * delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rsi = 100 - (100 / (1 + (gain / loss.replace(0, np.nan))))
        
        curr_p = float(close.iloc[-1])
        c_rsi = float(rsi.iloc[-1])
        
        # കണ്ടീഷനുകൾ പരിശോധിക്കുന്നു
        ema_ok = (curr_p > ema_f.iloc[-1] and ema_f.iloc[-1] > ema_s.iloc[-1]) if use_ema else True
        rsi_ok = (c_rsi > rsi_min) if use_rsi else True
        
        # വോളിയം പരിശോധന
        curr_vol = float(df['Volume'].iloc[-1])
        avg_vol = float(df['Volume'].iloc[-21:-1].mean())
        vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 0
        vol_ok = (vol_ratio > 1.5) if use_vol else True

        signal = "WAIT"
        if ema_ok and rsi_ok and vol_ok:
            # 20 ദിവസത്തെ ഹൈ പരിശോധിക്കുന്നു
            recent_high = float(df['High'].iloc[-21:-1].max())
            if smart_on and curr_p > recent_high:
                signal = "🚀 SMART BUY"
            else:
                signal = "✅ BUY"
        elif use_ema and curr_p < ema_s.iloc[-1]:
            signal = "⚠️ EXIT"
            
        return {
            "Ticker": ticker, 
            "Price": round(curr_p, 2), 
            "Signal": signal,
            "RSI": round(c_rsi, 1), 
            "Vol Ratio": round(vol_ratio, 2)
        }
    except: 
        return None

def style_signal(val):
    if "BUY" in str(val): return 'color: #28a745; font-weight: bold'
    if "EXIT" in str(val): return 'color: #dc3545; font-weight: bold'
    return ''

# --- 4. മെയിൻ ഇന്റർഫേസ് ---
def main():
    st.title("📈 HRC Pro Analyzer V5")

    # സൈഡ്‌ബാർ സെറ്റിംഗ്‌സ്
    st.sidebar.header("⚙️ Settings")
    f_n = st.sidebar.number_input("Fast EMA", value=50)
    s_n = st.sidebar.number_input("Slow EMA", value=200)
    rsi_val = st.sidebar.slider("Min RSI Limit", 20, 80, 45)
    
    st.sidebar.markdown("---")
    t_ema = st.sidebar.checkbox("EMA Filter", value=True)
    t_rsi = st.sidebar.checkbox("RSI Filter", value=True)
    t_vol = st.sidebar.checkbox("Volume Filter", value=True)
    t_smart = st.sidebar.checkbox("SMART BUY Mode", value=True)

    tab1, tab2 = st.tabs(["🔍 Market Scan", "💰 Portfolio"])

    with tab1:
        index_choice = st.selectbox("Select Index:", ["Nifty 50", "Nifty Next 50", "Nifty 100", "Nifty 500", "Nifty Bank", "Nifty IT"])
        stock_list = get_index_stocks(index_choice)
        
        if st.button(f"Scan {index_choice}", use_container_width=True):
            run_scanner(stock_list, f_n, s_n, rsi_val, t_ema, t_rsi, t_vol, t_smart)

    with tab2:
        p_input = st.text_area("സ്റ്റോക്കുകൾ നൽകുക (eg: SBIN, RELIANCE, TCS):", height=100)
        p_list = [s.strip().upper() for s in p_input.split(",") if s.strip()]
        if st.button("Scan My Portfolio", use_container_width=True):
            run_scanner(p_list, f_n, s_n, rsi_val, t_ema, t_rsi, t_vol, t_smart)

# --- 5. സ്കാനർ ഡിസ്‌പ്ലേ ---
def run_scanner(stocks, f_n, s_n, rsi_val, t_ema, t_rsi, t_vol, t_smart):
    results = []
    bar = st.progress(0)
    res_placeholder = st.empty()
    
    for i, ticker in enumerate(stocks):
        res = analyze_stock(ticker, f_n, s_n, rsi_val, t_ema, t_rsi, t_vol, t_smart)
        if res and res["Signal"] != "WAIT":
            results.append(res)
            # ലൈവ് ആയി ടേബിൾ അപ്‌ഡേറ്റ് ചെയ്യുന്നു
            df_res = pd.DataFrame(results)
            df_res.insert(0, 'No', range(1, len(df_res) + 1))
            res_placeholder.dataframe(df_res.style.applymap(style_signal, subset=['Signal']), use_container_width=True, hide_index=True)
            
        bar.progress((i + 1) / len(stocks))
    
    if not results:
        st.warning("നിബന്ധനകൾ പാലിക്കുന്ന സ്റ്റോക്കുകൾ ലഭ്യമല്ല.")

if __name__ == "__main__":
    main()
