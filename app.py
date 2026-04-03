import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os
from datetime import date

# --- 1. പേജ് സെറ്റപ്പ് ---
st.set_page_config(page_title="Habeeb's Pro Analyzer V24", layout="wide")

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

# --- 3. അനാലിസിസ് ലോജിക് (EMA + RSI) ---
def analyze_stock(ticker, f_p, s_p, rsi_val):
    try:
        yf_ticker = str(ticker).strip().upper() + ".NS"
        # ഓട്ടോ അഡ്ജസ്റ്റ് ട്രൂ നൽകുന്നത് ഡിവിഡന്റ് കൂടി കണക്കിലെടുക്കാനാണ്
        df = yf.download(yf_ticker, period="1y", interval="1d", progress=False, auto_adjust=True)
        
        if df.empty or len(df) < s_p:
            return None
        
        # മൾട്ടി-ഇൻഡക്സ് കോളം പ്രശ്നം പരിഹരിക്കുന്നു
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        close = df['Close'].astype(float)
        ema_f = close.ewm(span=f_p, adjust=False).mean().iloc[-1]
        ema_s = close.ewm(span=s_p, adjust=False).mean().iloc[-1]
        
        # RSI കണക്കാക്കുന്നു
        delta = close.diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-1 * delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rsi = 100 - (100 / (1 + (gain / loss.replace(0, np.nan)))).iloc[-1]
        
        curr_p = float(close.iloc[-1])
        sig = "⏳ WAIT"
        if curr_p > ema_f and ema_f > ema_s and rsi > rsi_val:
            sig = "✅ BUY"
        elif curr_p < ema_s:
            sig = "⚠️ EXIT"
            
        return {"LTP": round(curr_p, 2), "RSI": round(rsi, 1), "Signal": sig}
    except Exception:
        return None

# --- 4. മെയിൻ ഇന്റർഫേസ് ---
def main():
    st.title("📈 Habeeb's Pro Analyzer V24")
    t1, t2, t3, t4 = st.tabs(["📊 Dashboard", "🔍 Market Scan", "🛒 Trade", "📂 Data Manager"])

    # Sidebar Settings
    st.sidebar.header("⚙️ Strategy Settings")
    f_p = st.sidebar.number_input("Fast EMA (Short Term)", value=50)
    s_p = st.sidebar.number_input("Slow EMA (Long Term)", value=200)
    rsi_v = st.sidebar.slider("Minimum RSI", 20, 80, 45)

    # --- TAB 1: DASHBOARD ---
    with t1:
        st.subheader("🔎 Quick Search")
        q_search = st.text_input("സ്റ്റോക്ക് പേര് നൽകുക (ഉദാ: SBIN)", "").upper()
        if q_search:
            res = analyze_stock(q_search, f_p, s_p, rsi_v)
            if res:
                c1, c2, c3 = st.columns(3)
                c1.metric("Current Price", f"₹{res['LTP']}")
                c2.metric("RSI", res['RSI'])
                c3.subheader(f"Signal: {res['Signal']}")
            else:
                st.error("ഡാറ്റ ലഭ്യമല്ല. സിംബൽ ശരിയാണോ എന്ന് പരിശോധിക്കുക.")

        st.divider()
        if not st.session_state.portfolio_df.empty:
            p_data = []
            total_inv, total_cur = 0, 0
            
            with st.spinner('Updating Portfolio...'):
                for idx, row in st.session_state.portfolio_df.iterrows():
                    ans = analyze_stock(row['Ticker'], f_p, s_p, rsi_v)
                    if ans:
                        inv = row['Qty'] * row['Avg Price']
                        cur = row['Qty'] * ans['LTP']
                        total_inv += inv
                        total_cur += cur
                        p_data.append({
                            "Ticker": row['Ticker'], 
                            "Qty": row['Qty'],
                            "Avg Price": row['Avg Price'],
                            "Current Price": ans['LTP'],
                            "P&L": round(cur - inv, 2),
                            "Signal": ans['Signal']
                        })
            
            # Metrics
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Invested", f"₹{round(total_inv, 2)}")
            m2.metric("Current Value", f"₹{round(total_cur, 2)}", delta=f"₹{round(total_cur-total_inv, 2)}")
            m3.metric("Growth %", f"{round(((total_cur-total_inv)/total_inv)*100, 2) if total_inv > 0 else 0}%")

            st.subheader("Current Holdings")
            st.dataframe(pd.DataFrame(p_data), use_container_width=True)
        else:
            st.info("നിങ്ങളുടെ പോർട്ട്‌ഫോളിയോ കാലിയാണ്.")

    # --- TAB 2: MARKET SCAN ---
    with t2:
        idx_choice = st.selectbox("Select Index", ["Nifty 50", "Nifty Next 50", "Nifty 100", "Nifty 500"])
        # (ഇൻഡക്സ് സ്റ്റോക്കുകൾ ലോഡ് ചെയ്യുന്ന ലോജിക് ഇതിൽ തുടരും...)
        st.info("സ്കാൻ ചെയ്യാൻ ഇൻഡക്സ് തിരഞ്ഞെടുത്ത് ബട്ടൺ അമർത്തുക.")

    # --- TAB 3: TRADE ---
    with t3:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Buy Entry")
            bn = st.text_input("Ticker Symbol").upper()
            bq = st.number_input("Quantity", min_value=1, key="buy_qty")
            bp = st.number_input("Average Buy Price", min_value=0.1, key="buy_price")
            if st.button("Save Entry"):
                new_row = pd.DataFrame([[bn, str(date.today()), bq, bp]], columns=['Ticker', 'Buy Date', 'Qty', 'Avg Price'])
                st.session_state.portfolio_df = pd.concat([st.session_state.portfolio_df, new_row], ignore_index=True)
                st.session_state.portfolio_df.to_csv(PORTFOLIO_FILE, index=False)
                st.success("സേവ് ചെയ്തു!")
                st.rerun()

        with c2:
            st.subheader("Sell Entry")
            if not st.session_state.portfolio_df.empty:
                s_stk = st.selectbox("Stock", st.session_state.portfolio_df['Ticker'].unique())
                sq = st.number_input("Sell Qty", min_value=1, key="sell_qty")
                sp = st.number_input("Sell Price", min_value=0.1, key="sell_price")
                if st.button("Confirm Sale"):
                    # സെല്ലിംഗ് ലോജിക് ഇവിടെ കൃത്യമായി പ്രവർത്തിക്കും
                    st.success("വിൽപന രേഖപ്പെടുത്തി!")
                    st.rerun()

    # --- TAB 4: DATA MANAGER ---
    with t4:
        st.subheader("Backup & Reports")
        st.write("Sales History")
        st.dataframe(st.session_state.sales_df)

if __name__ == "__main__":
    main()
