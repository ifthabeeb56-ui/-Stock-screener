import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

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
        return ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"]

# --- 3. അനാലിസിസ് ലോജിക് ---
def analyze_stock(ticker, f_p, s_p, rsi_min, use_ema, use_rsi, use_vol, smart_on):
    try:
        symbol = str(ticker).split(':')[-1].strip().upper()
        yf_ticker = symbol + ".NS"
        
        # കുറച്ചുകൂടി സ്റ്റേബിൾ ആയ ഡൗൺലോഡ് രീതി
        stock = yf.Ticker(yf_ticker)
        df = stock.history(period="1y", interval="1d", auto_adjust=True)
        
        if df.empty or len(df) < s_p: return None
        
        close = df['Close'].astype(float)
        
        # EMA
        ema_f = close.ewm(span=f_p, adjust=False).mean()
        ema_s = close.ewm(span=s_p, adjust=False).mean()
        
        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-1 * delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rsi = 100 - (100 / (1 + (gain / loss.replace(0, np.nan))))
        
        curr_p = float(close.iloc[-1])
        c_rsi = float(rsi.iloc[-1])
        
        # Filters
        ema_ok = (curr_p > ema_f.iloc[-1] and ema_f.iloc[-1] > ema_s.iloc[-1]) if use_ema else True
        rsi_ok = (c_rsi > rsi_min) if use_rsi else True
        
        # Volume
        curr_vol = float(df['Volume'].iloc[-1])
        avg_vol = float(df['Volume'].iloc[-21:-1].mean())
        vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 0
        vol_ok = (vol_ratio > 1.5) if use_vol else True

        signal = "⏳ WAIT"
        if ema_ok and rsi_ok and vol_ok:
            recent_high = float(df['High'].iloc[-21:-1].max())
            if smart_on and curr_p > recent_high:
                signal = "🚀 SMART"
            else:
                signal = "✅ BUY"
        elif use_ema and curr_p < ema_s.iloc[-1]:
            signal = "⚠️ EXIT"
            
        return {"Ticker": symbol, "Price": round(curr_p, 1), "Signal": signal, "RSI": round(c_rsi, 1)}
    except: return None

# --- 4. കോംപാക്റ്റ് ഡിസ്‌പ്ലേ ---
def display_signal_box(sub_df):
    if not sub_df.empty:
        for _, row in sub_df.iterrows():
            ticker = row['Ticker']
            tv_url = f"https://www.tradingview.com/chart/?symbol=NSE:{ticker}"
            with st.container(border=True):
                # വരികൾക്കിടയിലുള്ള ഗ്യാപ്പ് കുറച്ചു
                st.markdown(f"**[{ticker}]({tv_url})** | ₹{row['Price']} | RSI: {row['RSI']}")
    else:
        st.write("Nil")

# --- 5. മെയിൻ ഇന്റർഫേസ് ---
def main():
    st.title("📈 HRC Pro Analyzer V5")

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
        p_input = st.text_area("Symbols (SBIN, RELIANCE...):", height=100)
        p_list = [s.strip().upper() for s in p_input.split(",") if s.strip()]
        if st.button("Scan My Portfolio", use_container_width=True):
            run_scanner(p_list, f_n, s_n, rsi_val, t_ema, t_rsi, t_vol, t_smart)

# --- 6. സ്കാനർ ഡിസ്‌പ്ലേ ---
def run_scanner(stocks, f_n, s_n, rsi_val, t_ema, t_rsi, t_vol, t_smart):
    all_results = []
    bar = st.progress(0)
    status_text = st.empty()
    
    for i, ticker in enumerate(stocks):
        status_text.caption(f"Scanning: {ticker}...")
        res = analyze_stock(ticker, f_n, s_n, rsi_val, t_ema, t_rsi, t_vol, t_smart)
        if res: all_results.append(res)
        bar.progress((i + 1) / len(stocks))
    
    status_text.empty()

    if all_results:
        df = pd.DataFrame(all_results)
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.success("### ✅ BUY")
            display_signal_box(df[df['Signal'] == "✅ BUY"])

        with col2:
            st.info("### 🚀 SMART")
            display_signal_box(df[df['Signal'] == "🚀 SMART"])

        with col3:
            st.error("### ⚠️ EXIT")
            display_signal_box(df[df['Signal'] == "⚠️ EXIT"])

        with col4:
            st.warning("### ⏳ WAIT")
            display_signal_box(df[df['Signal'] == "⏳ WAIT"])
    else:
        st.warning("Data download failed or no stocks found.")

if __name__ == "__main__":
    main()
