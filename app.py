import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

# --- 1. പേജ് സെറ്റപ്പ് ---
st.set_page_config(page_title="HRC Pro Analyzer V5", layout="wide")

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
        vol = df['Volume'].astype(float)
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
            avg_v = vol.iloc[i-21:i].mean()
            vol_ok = vol.iloc[i] > (avg_v * 1.5) if avg_v > 0 else True

            if not in_pos:
                if curr_p > ema_f.iloc[i] and ema_f.iloc[i] > ema_s.iloc[i] and rsi.iloc[i] > rsi_min and vol_ok:
                    in_pos, buy_p = True, curr_p
            elif in_pos:
                if curr_p < ema_s.iloc[i]:
                    trades.append(((curr_p - buy_p) / buy_p) * 100)
                    in_pos = False
                    
        if trades:
            win_r = (len([t for t in trades if t > 0]) / len(trades)) * 100
            return len(trades), round(win_r, 1), round(sum(trades)/len(trades), 1)
        return 0, 0, 0
    except: return 0, 0, 0

# --- 4. അനാലിസിസ് ലോജിക് ---
def analyze_stock(ticker, f_p, s_p, rsi_min, use_ema, use_rsi, use_vol, smart_on):
    try:
        symbol = str(ticker).strip().upper()
        df = yf.download(symbol + ".NS", period="1y", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < s_p: return None
        
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        close = df['Close'].astype(float)
        
        ema_f, ema_s = close.ewm(span=f_p, adjust=False).mean(), close.ewm(span=s_p, adjust=False).mean()
        delta = close.diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-1 * delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rsi = 100 - (100 / (1 + (gain / loss.replace(0, np.nan))))
        
        curr_p, c_rsi = float(close.iloc[-1]), float(rsi.iloc[-1])
        ema_ok = (curr_p > ema_f.iloc[-1] and ema_f.iloc[-1] > ema_s.iloc[-1]) if use_ema else True
        rsi_ok = (c_rsi > rsi_min) if use_rsi else True
        avg_vol = float(df['Volume'].iloc[-21:-1].mean())
        vol_ok = (float(df['Volume'].iloc[-1]) / avg_vol > 1.5) if use_vol and avg_vol > 0 else True

        signal = "⏳ WAIT"
        if ema_ok and rsi_ok and vol_ok:
            signal = "🚀 SMART" if (smart_on and curr_p > float(df['High'].iloc[-21:-1].max())) else "✅ BUY"
        elif use_ema and curr_p < ema_s.iloc[-1]: signal = "⚠️ EXIT"

        t_count, win_r, avg_p = perform_backtest(df, f_p, s_p, rsi_min)
        return {"Ticker": symbol, "Price": round(curr_p, 1), "Signal": signal, "RSI": round(c_rsi, 1), 
                "Trades": t_count, "Win_Rate%": win_r, "Avg_Profit%": avg_p}
    except: return None

# --- 5. സിഗ്നൽ ബോക്സ് ---
def display_signal_box(sub_df):
    if not sub_df.empty:
        for _, row in sub_df.iterrows():
            ticker = row['Ticker']
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"**[{ticker}](https://www.tradingview.com/chart/?symbol=NSE:{ticker})** | ₹{row['Price']}")
                    st.caption(f"Win: {row['Win_Rate%']}% | Trades: {row['Trades']}")
                with c2:
                    # ബട്ടൺ യൂണിക് ആകാൻ സിഗ്നൽ ടാഗ് കൂടി കീയിൽ ചേർത്തു
                    if st.button("➕", key=f"bt_{ticker}_{row['Signal']}"):
                        if ticker not in st.session_state.watchlist:
                            st.session_state.watchlist.append(ticker)
                            st.rerun()
    else: st.write("Nil")

# --- 6. മെയിൻ ഇന്റർഫേസ് ---
def main():
    st.title("📈 HRC Pro Analyzer V5")
    st.sidebar.header("⚙️ Settings")
    f_n = st.sidebar.number_input("Fast EMA", value=50)
    s_n = st.sidebar.number_input("Slow EMA", value=200)
    rsi_val = st.sidebar.slider("Min RSI Limit", 20, 80, 45)
    t_ema, t_rsi = st.sidebar.checkbox("EMA Filter", True), st.sidebar.checkbox("RSI Filter", True)
    t_vol, t_smart = st.sidebar.checkbox("Volume Filter", True), st.sidebar.checkbox("SMART BUY Mode", True)

    if st.session_state.watchlist:
        with st.sidebar.expander("⭐ Watchlist", expanded=True):
            for w in st.session_state.watchlist: st.write(f"• {w}")
            if st.button("Clear All"): st.session_state.watchlist = []; st.rerun()

    tab1, tab2 = st.tabs(["🔍 Market Scan", "💰 Portfolio"])
    with tab1:
        idx = st.selectbox("Select Index:", ["Nifty 50", "Nifty Next 50", "Nifty 100", "Nifty 500", "Nifty Bank", "Nifty IT"])
        if st.button(f"Scan {idx}", use_container_width=True):
            run_scanner(get_index_stocks(idx), f_n, s_n, rsi_val, t_ema, t_rsi, t_vol, t_smart)
    with tab2:
        p_in = st.text_area("Symbols (SBIN, RELIANCE...):", height=80)
        combined = list(set([s.strip().upper() for s in p_in.split(",") if s.strip()] + st.session_state.watchlist))
        if st.button("Analyze Portfolio", use_container_width=True):
            run_scanner(combined, f_n, s_n, rsi_val, t_ema, t_rsi, t_vol, t_smart)

# --- 7. സ്കാനർ ഔട്ട്‌പുട്ട് (പൂർണ്ണരൂപം) ---
def run_scanner(stocks, f_n, s_n, rsi_val, t_ema, t_rsi, t_vol, t_smart):
    results = []
    bar = st.progress(0)
    status = st.empty()
    for i, t in enumerate(stocks):
        status.caption(f"Analyzing {t}...")
        res = analyze_stock(t, f_n, s_n, rsi_val, t_ema, t_rsi, t_vol, t_smart)
        if res: results.append(res)
        bar.progress((i + 1) / len(stocks))
    status.empty()
    
    if results:
        df = pd.DataFrame(results)
        st.download_button("📥 Download Full Report", df.to_csv(index=False).encode('utf-8'), "full_report.csv", "text/csv")

        st.markdown("---")
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.success("### ✅ BUY")
            d_buy = df[df['Signal'] == "✅ BUY"]
            if not d_buy.empty:
                st.download_button("📥 CSV", d_buy.to_csv(index=False).encode('utf-8'), "buy.csv", key="dl_b")
            display_signal_box(d_buy)

        with c2:
            st.info("### 🚀 SMART")
            d_smart = df[df['Signal'] == "🚀 SMART"]
            if not d_smart.empty:
                st.download_button("📥 CSV", d_smart.to_csv(index=False).encode('utf-8'), "smart.csv", key="dl_s")
            display_signal_box(d_smart)

        with c3:
            st.error("### ⚠️ EXIT")
            d_exit = df[df['Signal'] == "⚠️ EXIT"]
            if not d_exit.empty:
                st.download_button("📥 CSV", d_exit.to_csv(index=False).encode('utf-8'), "exit.csv", key="dl_e")
            display_signal_box(d_exit)

        with c4:
            st.warning("### ⏳ WAIT")
            display_signal_box(df[df['Signal'] == "⏳ WAIT"])
        
        st.markdown("---")
        st.subheader("📋 Detailed Scanned List")
        df_display = df.copy()
        df_display.insert(0, 'Sl. No', range(1, len(df_display) + 1))
        
        def color_signal(val):
            colors = {"✅ BUY": "#28a745", "🚀 SMART": "#007bff", "⚠️ EXIT": "#dc3545", "⏳ WAIT": "#ffc107"}
            return f'color: {colors.get(val, "white")}; font-weight: bold'

        st.dataframe(df_display.style.map(color_signal, subset=['Signal']), use_container_width=True, hide_index=True)
    else: 
        st.warning("No data found.")

if __name__ == "__main__": 
    main()
