import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import os
from datetime import date

# --- 1. പേജ് സെറ്റപ്പ് ---
st.set_page_config(page_title="Habeeb's Pro Analyzer V5", layout="wide")

PORTFOLIO_FILE = "my_portfolio.csv"

# --- 2. ഡാറ്റ മാനേജ്‌മെന്റ് ---
def load_data():
    if os.path.exists(PORTFOLIO_FILE):
        return pd.read_csv(PORTFOLIO_FILE)
    return pd.DataFrame(columns=['Ticker', 'Buy Date', 'Qty', 'Avg Price'])

@st.cache_data(ttl=86400)
def get_index_stocks(index_name):
    indices = {
        "Nifty 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        "Nifty 100": "https://archives.nseindia.com/content/indices/ind_nifty100list.csv",
        "Nifty 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    }
    try:
        url = indices.get(index_name)
        df = pd.read_csv(url)
        col = 'Symbol' if 'Symbol' in df.columns else df.columns[0]
        return df[col].str.strip().tolist()
    except:
        return ["RELIANCE", "TCS", "SBIN", "INFY", "TATAMOTORS"]

# --- 3. അനാലിസിസ് ലോജിക് ---
def analyze_stock(ticker, f_p, s_p, rsi_val):
    try:
        yf_ticker = str(ticker).strip().upper() + ".NS"
        df = yf.download(yf_ticker, period="1y", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < s_p: return None
        
        # കോളങ്ങൾ സിംഗിൾ ഇൻഡക്‌സ് ആണെന്ന് ഉറപ്പാക്കുന്നു
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
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
            
        return {"Ticker": ticker, "LTP": round(curr_p, 2), "RSI": round(rsi, 1), "Signal": sig}
    except: return None

# --- 4. മെയിൻ ഇന്റർഫേസ് ---
def main():
    st.title("📈 Habeeb's Pro Analyzer V5")

    st.sidebar.header("⚙️ Settings")
    f_p = st.sidebar.number_input("Fast EMA", value=50)
    s_p = st.sidebar.number_input("Slow EMA", value=200)
    rsi_v = st.sidebar.slider("Min RSI", 20, 80, 45)

    tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "🔍 Market Scan", "🛒 Trade Manager"])

    # --- TAB 1: DASHBOARD ---
    with tab1:
        df_p = load_data()
        if not df_p.empty:
            st.subheader("Your Portfolio Status")
            p_display = []
            for _, row in df_p.iterrows():
                live = analyze_stock(row['Ticker'], f_p, s_p, rsi_v)
                if live:
                    profit = (live['LTP'] - row['Avg Price']) * row['Qty']
                    perc = ((live['LTP'] - row['Avg Price']) / row['Avg Price']) * 100
                    p_display.append({
                        "Ticker": row['Ticker'], "Qty": row['Qty'], "Avg Price": row['Avg Price'],
                        "LTP": live['LTP'], "Profit": round(profit, 2), "P&L %": f"{round(perc, 2)}%",
                        "Signal": live['Signal']
                    })
            st.dataframe(pd.DataFrame(p_display), use_container_width=True, hide_index=True)
        else:
            st.info("പോർട്ട്‌ഫോളിയോ കാലിയാണ്.")

    # --- TAB 2: MARKET SCAN ---
    with tab2:
        idx_choice = st.selectbox("ഇൻഡക്സ്:", ["Nifty 50", "Nifty 100", "Nifty 500"])
        if st.button("🚀 Start Scan"):
            stocks = get_index_stocks(idx_choice)
            results = []
            bar = st.progress(0)
            placeholder = st.empty()
            for i, tkr in enumerate(stocks):
                res = analyze_stock(tkr, f_p, s_p, rsi_v)
                if res:
                    results.append(res)
                    placeholder.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
                bar.progress((i + 1) / len(stocks))
            
            buys = [r['Ticker'] for r in results if r['Signal'] == "✅ BUY"]
            if buys: st.success(f"വാങ്ങാൻ അനുയോജ്യമായവ: {', '.join(buys)}")

    # --- TAB 3: TRADE MANAGER ---
    with tab3:
        st.subheader("Add Stock Entry")
        with st.form("buy_form", clear_on_submit=True):
            bn = st.text_input("Ticker Symbol").upper()
            bq = st.number_input("Quantity", min_value=1)
            bp = st.number_input("Buy Price", min_value=1.0)
            if st.form_submit_button("Save"):
                if bn:
                    df_p = load_data()
                    if bn in df_p['Ticker'].values:
                        idx = df_p[df_p['Ticker'] == bn].index[0]
                        old_qty = df_p.at[idx, 'Qty']
                        old_price = df_p.at[idx, 'Avg Price']
                        new_total_qty = old_qty + bq
                        new_avg_price = ((old_qty * old_price) + (bq * bp)) / new_total_qty
                        df_p.at[idx, 'Qty'] = new_total_qty
                        df_p.at[idx, 'Avg Price'] = round(new_avg_price, 2)
                    else:
                        new_row = pd.DataFrame([[bn, str(date.today()), bq, bp]], columns=['Ticker', 'Buy Date', 'Qty', 'Avg Price'])
                        df_p = pd.concat([df_p, new_row], ignore_index=True)
                    df_p.to_csv(PORTFOLIO_FILE, index=False)
                    st.success(f"{bn} അപ്‌ഡേറ്റ് ചെയ്തു!")
                    st.rerun()

if __name__ == "__main__":
    main()
