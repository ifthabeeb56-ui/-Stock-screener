import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os
from datetime import date

# --- 1. പേജ് സെറ്റപ്പ് ---
st.set_page_config(page_title="Habeeb's Pro Analyzer V25", layout="wide")

# ഫയൽ പാത്തുകൾ
PORTFOLIO_FILE = "my_portfolio.csv"
SALES_FILE = "sales_history.csv"

# --- 2. ഡാറ്റ ലോഡിംഗ് ---
def load_data():
    if 'portfolio_df' not in st.session_state:
        if os.path.exists(PORTFOLIO_FILE):
            st.session_state.portfolio_df = pd.read_csv(PORTFOLIO_FILE)
        else:
            st.session_state.portfolio_df = pd.DataFrame(columns=['Ticker', 'Buy Date', 'Qty', 'Avg Price'])
    
    if 'sales_df' not in st.session_state:
        if os.path.exists(SALES_FILE):
            st.session_state.sales_df = pd.read_csv(SALES_FILE)
        else:
            st.session_state.sales_df = pd.DataFrame(columns=['Ticker', 'Sell Date', 'Qty', 'Sell Price', 'Profit/Loss'])

load_data()

# --- 3. ഇൻഡക്സ് ലോഡിംഗ് ---
@st.cache_data(ttl=86400)
def get_index_stocks(index_name):
    indices = {
        "Nifty 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        "Nifty Next 50": "https://archives.nseindia.com/content/indices/ind_niftynext50list.csv",
        "Nifty 100": "https://archives.nseindia.com/content/indices/ind_nifty100list.csv",
        "Nifty 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    }
    try:
        df = pd.read_csv(indices.get(index_name))
        col = 'Symbol' if 'Symbol' in df.columns else df.columns[0]
        return df[col].str.strip().tolist()
    except:
        return ["RELIANCE", "TCS", "SBIN", "INFY", "TATAMOTORS"]

# --- 4. അനാലിസിസ് ലോജിക് (EMA + RSI) ---
def analyze_stock(ticker, f_p, s_p, rsi_val):
    try:
        yf_ticker = str(ticker).strip().upper() + ".NS"
        df = yf.download(yf_ticker, period="1y", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < s_p: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        close = df['Close'].astype(float)
        ema_f = close.ewm(span=f_p, adjust=False).mean().iloc[-1]
        ema_s = close.ewm(span=s_p, adjust=False).mean().iloc[-1]
        
        delta = close.diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-1 * delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rsi = 100 - (100 / (1 + (gain / loss.replace(0, np.nan)))).iloc[-1]
        
        curr_p = float(close.iloc[-1])
        sig = "⏳ WAIT"
        if curr_p > ema_f and ema_f > ema_s and rsi > rsi_val: sig = "✅ BUY"
        elif curr_p < ema_s: sig = "⚠️ EXIT"
            
        return {"LTP": round(curr_p, 2), "RSI": round(rsi, 1), "Signal": sig}
    except: return None

# --- 5. മെയിൻ ഇന്റർഫേസ് ---
def main():
    st.title("📈 Habeeb's Pro Analyzer V25")
    t1, t2, t3, t4 = st.tabs(["📊 Dashboard", "🔍 Market Scan", "🛒 Trade", "📂 Data Manager"])

    st.sidebar.header("⚙️ Settings")
    f_p = st.sidebar.number_input("Fast EMA", value=50)
    s_p = st.sidebar.number_input("Slow EMA", value=200)
    rsi_v = st.sidebar.slider("Min RSI", 20, 80, 45)

    # --- TAB 1: DASHBOARD (സെർച്ച് ബാർ ഇവിടെയുണ്ട്) ---
    with t1:
        st.subheader("🔎 Quick Stock Check")
        q_search = st.text_input("സ്റ്റോക്ക് പേര് ടൈപ്പ് ചെയ്യുക (ഉദാ: SBIN)", "").upper()
        if q_search:
            res = analyze_stock(q_search, f_p, s_p, rsi_v)
            if res:
                c1, c2, c3 = st.columns(3)
                c1.metric("Price", f"₹{res['LTP']}")
                c2.metric("RSI", res['RSI'])
                c3.subheader(f"Signal: {res['Signal']}")
            else: st.error("Data not found!")

        st.divider()
        if not st.session_state.portfolio_df.empty:
            st.subheader("My Portfolio Status")
            # പോർട്ട്‌ഫോളിയോ ലോജിക് ഇവിടെ തുടരും...
            st.dataframe(st.session_state.portfolio_df, use_container_width=True)
        else: st.info("Portfolio is empty.")

    # --- TAB 2: MARKET SCAN ---
    with t2:
        idx_choice = st.selectbox("Select Index", ["Nifty 50", "Nifty Next 50", "Nifty 100", "Nifty 500"])
        stock_list = get_index_stocks(idx_choice)
        if st.button(f"🚀 Start Scan ({len(stock_list)} Stocks)"):
            results = []
            bar = st.progress(0)
            placeholder = st.empty()
            for i, tkr in enumerate(stock_list):
                res = analyze_stock(tkr, f_p, s_p, rsi_v)
                if res:
                    res['Ticker'] = tkr
                    results.append(res)
                    placeholder.dataframe(pd.DataFrame(results), use_container_width=True)
                bar.progress((i + 1) / len(stock_list))

    # --- TAB 3: TRADE ---
    with t3:
        st.subheader("Buy/Sell Records")
        # ഇവിടെയാണ് നിങ്ങൾ വാങ്ങിയ സ്റ്റോക്കുകൾ ആഡ് ചെയ്യേണ്ടത്.
        c1, c2 = st.columns(2)
        with c1:
            bn = st.text_input("Ticker").upper()
            bq = st.number_input("Qty", min_value=1)
            bp = st.number_input("Price", min_value=1.0)
            if st.button("Save Buy"):
                new_row = pd.DataFrame([[bn, str(date.today()), bq, bp]], columns=['Ticker', 'Buy Date', 'Qty', 'Avg Price'])
                st.session_state.portfolio_df = pd.concat([st.session_state.portfolio_df, new_row], ignore_index=True)
                st.session_state.portfolio_df.to_csv(PORTFOLIO_FILE, index=False)
                st.success("Saved!")

    # --- TAB 4: DATA MANAGER ---
    with t4:
        st.subheader("History & Files")
        st.dataframe(st.session_state.sales_df)
        if st.button("Clear All Data"):
            if os.path.exists(PORTFOLIO_FILE): os.remove(PORTFOLIO_FILE)
            st.rerun()

if __name__ == "__main__":
    main()
