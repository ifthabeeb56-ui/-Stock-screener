import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- 1. പേജ് സെറ്റപ്പ് ---
st.set_page_config(page_title="Habeeb's Pro Analyzer V5", layout="wide")

# --- 2. ഇൻഡക്സുകൾ ലോഡ് ചെയ്യുന്ന ഫംഗ്‌ഷൻ ---
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
        return ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"]

# --- 3. ഇൻഡിക്കേറ്റർ കാൽക്കുലേഷൻ ---
def calculate_indicators(df, f_period, s_period):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    close = df['Close'].astype(float)
    ema_f = close.ewm(span=f_period, adjust=False).mean()
    ema_s = close.ewm(span=s_period, adjust=False).mean()
    
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
    rs = avg_gain / (avg_loss.replace(0, np.nan))
    rsi = 100 - (100 / (1 + rs))
    return ema_f, ema_s, rsi.fillna(50)

# --- 4. അനാലിസിസ് ലോജിക് ---
def analyze_stock(ticker, f_p, s_p, rsi_min, use_ema, use_rsi, use_vol, smart_on):
    try:
        yf_ticker = str(ticker).strip() + ".NS"
        df = yf.download(yf_ticker, period="1y", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < s_p: return None
        
        ema_f, ema_s, rsi = calculate_indicators(df, f_p, s_p)
        curr_price = float(df['Close'].iloc[-1])
        c_rsi = float(rsi.iloc[-1])
        
        # ഫിൽട്ടറുകൾ പ്രയോഗിക്കുന്നു
        ema_ok = (curr_price > ema_f.iloc[-1] and ema_f.iloc[-1] > ema_s.iloc[-1]) if use_ema else True
        rsi_ok = (c_rsi > rsi_min) if use_rsi else True
        
        curr_vol = float(df['Volume'].iloc[-1])
        avg_vol = float(df['Volume'].iloc[-21:-1].mean())
        vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 0
        vol_ok = (vol_ratio > 1.5) if use_vol else True

        # സ്മാർട്ട് ബായ് കണ്ടീഷൻസ്
        df_w = df.resample('W').last()
        w_ema = df_w['Close'].ewm(span=30, adjust=False).mean().iloc[-1]
        is_weekly_bullish = df_w['Close'].iloc[-1] > w_ema
        recent_high = float(df['High'].iloc[-21:-1].max())

        signal = "WAIT"
        if smart_on and ema_ok and rsi_ok and vol_ok and is_weekly_bullish and curr_price > recent_high:
            signal = "🚀 SMART BUY"
        elif ema_ok and rsi_ok and vol_ok:
            signal = "✅ BUY"
        elif use_ema and curr_price < ema_s.iloc[-1]:
            signal = "⚠️ EXIT"
            
        if signal == "WAIT": return None
        
        return {
            "Ticker": ticker, "Price": round(curr_price, 2), "Signal": signal,
            "RSI": round(c_rsi, 1), "Vol Ratio": round(vol_ratio, 2)
        }
    except: return None

# --- 5. മെയിൻ ഇന്റർഫേസ് ---
def main():
    st.title("📈 Habeeb's Pro Analyzer V5")

    # മൂന്ന് ടാബുകൾ
    tab1, tab2, tab3 = st.tabs(["🔍 Market Scan", "💰 Portfolio", "👀 Watchlist"])

    # Sidebar settings
    st.sidebar.header("⚙️ Global Settings")
    f_n = st.sidebar.number_input("Fast EMA", value=50)
    s_n = st.sidebar.number_input("Slow EMA", value=200)
    rsi_val = st.sidebar.slider("Min RSI", 20, 80, 45)
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("Filters Control")
    t_ema = st.sidebar.checkbox("Enable EMA Filter", value=True)
    t_rsi = st.sidebar.checkbox("Enable RSI Filter", value=True)
    t_vol = st.sidebar.checkbox("Enable Volume Filter", value=True)
    t_smart = st.sidebar.checkbox("Enable 🚀 SMART BUY", value=True)

    # --- TAB 1: FULL SCAN ---
    with tab1:
        index_choice = st.selectbox("ഇൻഡക്സ് തിരഞ്ഞെടുക്കുക:", ["Nifty 50", "Nifty Next 50", "Nifty 100", "Nifty 500", "Nifty Bank", "Nifty IT"])
        stock_list = get_index_stocks(index_choice)
        if st.button(f"🚀 Start Full Scan ({len(stock_list)} Stocks)", key="btn1", use_container_width=True):
            run_scanner(stock_list, f_n, s_n, rsi_val, t_ema, t_rsi, t_vol, t_smart)

    # --- TAB 2: PORTFOLIO ---
    with tab2:
        p_input = st.text_area("വാങ്ങിയ സ്റ്റോക്കുകൾ നൽകുക (കോമ ഉപയോഗിക്കുക):", "RELIANCE, HDFCBANK, TATASTEEL", key="p_box", height=150)
        p_list = [s.strip().upper() for s in p_input.split(",") if s.strip()]
        if st.button(f"🔍 Check Portfolio ({len(p_list)})", key="btn2", use_container_width=True):
            run_scanner(p_list, f_n, s_n, rsi_val, t_ema, t_rsi, t_vol, t_smart)

    # --- TAB 3: WATCHLIST ---
    with tab3:
        w_input = st.text_area("നിരീക്ഷിക്കുന്ന സ്റ്റോക്കുകൾ നൽകുക (കോമ ഉപയോഗിക്കുക):", "TCS, SBIN, INFY", key="w_box", height=150)
        w_list = [s.strip().upper() for s in w_input.split(",") if s.strip()]
        if st.button(f"🔍 Check Watchlist ({len(w_list)})", key="btn3", use_container_width=True):
            run_scanner(w_list, f_n, s_n, rsi_val, t_ema, t_rsi, t_vol, t_smart)

# --- 6. സ്കാനർ ഫംഗ്‌ഷൻ (Alignment Fix) ---
def run_scanner(stocks, f_n, s_n, rsi_val, t_ema, t_rsi, t_vol, t_smart):
    results = []
    bar = st.progress(0)
    res_container = st.empty()
    
    for i, ticker in enumerate(stocks):
        res = analyze_stock(ticker, f_n, s_n, rsi_val, t_ema, t_rsi, t_vol, t_smart)
        if res:
            results.append(res)
            df_display = pd.DataFrame(results)
            df_display.insert(0, 'Sl No', range(1, len(df_display) + 1))
            
            # അലൈൻമെന്റ് സെന്ററിലാക്കാൻ column_config കൃത്യമായി നൽകുന്നു
            res_container.dataframe(
                df_display.sort_values(by="Signal", ascending=False),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Sl No": st.column_config.Column("Sl No", width="small"),
                    "Ticker": st.column_config.Column("Ticker", width="medium"),
                    "Price": st.column_config.NumberColumn("Price", format="₹%.2f"),
                    "Signal": st.column_config.Column("Signal", width="medium"),
                    "RSI": st.column_config.NumberColumn("RSI", format="%.1f"),
                    "Vol Ratio": st.column_config.NumberColumn("Vol Ratio", format="%.2f")
                }
            )
        bar.progress((i + 1) / len(stocks))
    
    if not results:
        st.warning("നിബന്ധനകൾക്ക് അനുയോജ്യമായ സ്റ്റോക്കുകൾ കണ്ടില്ല.")
    else:
        st.success(f"ആകെ {len(results)} സ്റ്റോക്കുകൾ കണ്ടെത്തി.")

if __name__ == "__main__":
    main()
