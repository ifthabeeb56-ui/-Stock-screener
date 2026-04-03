import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import os
from datetime import date

# --- 1. പേജ് സെറ്റപ്പ് ---
st.set_page_config(page_title="Habeeb's Pro Analyzer V4", layout="wide")

# ഫയൽ പാത്തുകൾ
PORTFOLIO_FILE = "my_portfolio.csv"

# --- 2. ഡാറ്റ ലോഡിംഗ് ഫംഗ്‌ഷൻ ---
def load_data():
    if os.path.exists(PORTFOLIO_FILE):
        return pd.read_csv(PORTFOLIO_FILE)
    return pd.DataFrame(columns=['Ticker', 'Buy Date', 'Qty', 'Avg Price'])

# --- 3. അനാലിസിസ് ലോജിക് (EMA + RSI) ---
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

# --- 4. മെയിൻ ഇന്റർഫേസ് ---
def main():
    st.title("📈 Habeeb's Pro Analyzer V4 (Updated)")

    # സൈഡ്‌ബാർ സെറ്റിംഗ്‌സ്
    st.sidebar.header("⚙️ Strategy Settings")
    f_p = st.sidebar.number_input("Fast EMA", value=50)
    s_p = st.sidebar.number_input("Slow EMA", value=200)
    rsi_v = st.sidebar.slider("Min RSI", 20, 80, 45)

    # ടാബുകൾ
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard & Search", "🔍 Full Scan", "🛒 Trade Manager"])

    # --- TAB 1: DASHBOARD & QUICK SEARCH ---
    with tab1:
        st.subheader("🔎 Quick Stock Check")
        q_search = st.text_input("സ്റ്റോക്ക് പേര് ടൈപ്പ് ചെയ്യുക (eg: SBIN, RELIANCE)", "").upper()
        if q_search:
            res = analyze_stock(q_search, f_p, s_p, rsi_v)
            if res:
                c1, c2, c3 = st.columns(3)
                c1.metric("Current Price", f"₹{res['LTP']}")
                c2.metric("RSI", res['RSI'])
                c3.subheader(f"Signal: {res['Signal']}")
            else: st.error("ഡാറ്റ ലഭ്യമല്ല. പേര് ശരിയാണോ എന്ന് നോക്കൂ.")
        
        st.divider()
        st.subheader("Your Current Holdings")
        df_p = load_data()
        if not df_p.empty:
            st.dataframe(df_p, use_container_width=True)
        else: st.info("പോർട്ട്‌ഫോളിയോ കാലിയാണ്.")

    # --- TAB 2: FULL SCAN ---
    with tab2:
        st.subheader("Market Scan")
        index_choice = st.selectbox("Select Index", ["Nifty 50", "Nifty 100", "Nifty 500"])
        # (സ്കാനിംഗ് ലോജിക് ഇവിടെ തുടരും...)
        st.info("ഇൻഡക്സ് തിരഞ്ഞെടുത്ത് സ്കാൻ ബട്ടൺ അമർത്തുക.")

    # --- TAB 3: TRADE MANAGER ---
    with tab3:
        st.subheader("Add Stock to Portfolio")
        with st.form("buy_form", clear_on_submit=True):
            bn = st.text_input("Ticker Name").upper()
            bq = st.number_input("Quantity", min_value=1)
            bp = st.number_input("Average Price", min_value=1.0)
            if st.form_submit_button("Save to Portfolio"):
                df_p = load_data()
                new_row = pd.DataFrame([[bn, str(date.today()), bq, bp]], columns=['Ticker', 'Buy Date', 'Qty', 'Avg Price'])
                updated_df = pd.concat([df_p, new_row], ignore_index=True)
                updated_df.to_csv(PORTFOLIO_FILE, index=False)
                st.success(f"{bn} സേവ് ചെയ്തു!")
                st.rerun()

if __name__ == "__main__":
    main()
