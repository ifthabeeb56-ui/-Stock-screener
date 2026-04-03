import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- 1. പേജ് സെറ്റപ്പ് ---
st.set_page_config(page_title="Habeeb's Power Screener", layout="wide")

@st.cache_data
def load_stock_list():
    try:
        # csv ഫയലിൽ 'Ticker' എന്ന കോളം ഉണ്ടെന്ന് ഉറപ്പാക്കുക
        df = pd.read_csv("nifty_list.csv")
        df.columns = df.columns.str.strip()
        return df['Ticker'].unique().tolist()
    except Exception as e:
        st.error(f"Error loading CSV: {e}")
        return []

# --- 2. ഇൻഡിക്കേറ്റർ കാൽക്കുലേഷൻ (Manual RSI & EMA) ---
def calculate_custom_indicators(df, f_period, s_period):
    # MultiIndex ഒഴിവാക്കാൻ
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    close = df['Close'].astype(float)
    
    # EMAs
    ema_f = close.ewm(span=f_period, adjust=False).mean()
    ema_s = close.ewm(span=s_period, adjust=False).mean()
    
    # Standard RSI (Wilder's Smoothing)
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)
    
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
    
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    
    return ema_f, ema_s, rsi.fillna(50)

# --- 3. സ്റ്റോക്ക് അനാലിസിസ് (Format Fix Included) ---
def analyze_stock(ticker, f_ema, s_ema, rsi_min):
    try:
        # നിങ്ങളുടെ ലിസ്റ്റിലെ 'NSE:SYMBOL' എന്നതിനെ 'SYMBOL.NS' എന്നാക്കി മാറ്റുന്നു
        # ഉദാഹരണം: NSE:RVNL -> RVNL.NS
        clean_ticker = str(ticker).replace("NSE:", "").strip() + ".NS"
        
        # ഡാറ്റ ഡൗൺലോഡ് ചെയ്യുന്നു
        df = yf.download(clean_ticker, period="1y", interval="1d", progress=False, auto_adjust=True)
        
        if df.empty or len(df) < s_ema:
            return None
        
        df = df.dropna()
        ema_f, ema_s, rsi = calculate_custom_indicators(df, f_ema, s_ema)
        
        curr_price = float(df['Close'].iloc[-1])
        c_ema_f = float(ema_f.iloc[-1])
        c_ema_s = float(ema_s.iloc[-1])
        c_rsi = float(rsi.iloc[-1])

        # കണ്ടീഷൻസ്:
        # 1. Fast EMA > Slow EMA
        # 2. RSI > Minimum Limit
        # 3. Price > Fast EMA
        if (c_ema_f > c_ema_s) and (c_rsi > rsi_min) and (curr_price > c_ema_f):
            return {
                "Ticker": ticker, # ഒറിജിനൽ പേര് തന്നെ കാണിക്കാൻ
                "Symbol": clean_ticker, # മാറിയ പേര്
                "Price": round(curr_price, 2),
                "RSI": round(c_rsi, 1),
                f"EMA {f_ema}": round(c_ema_f, 1),
                f"EMA {s_ema}": round(c_ema_s, 1)
            }
    except Exception:
        return None
    return None

# --- 4. മെയിൻ ഇന്റർഫേസ് ---
def main():
    st.title("📈 Customizable Power Screener")
    st.markdown("---")
    
    # Sidebar Settings
    st.sidebar.header("⚙️ സ്കാനർ സെറ്റിംഗ്സ്")
    fast_n = st.sidebar.number_input("Fast EMA", min_value=5, max_value=100, value=50)
    slow_n = st.sidebar.number_input("Slow EMA", min_value=20, max_value=500, value=200)
    rsi_n = st.sidebar.slider("മിനിമം RSI", 30, 85, 60)
    
    stock_list = load_stock_list()
    
    if not stock_list:
        st.error("nifty_list.csv ഫയൽ പരിശോധിക്കുക.")
        return

    scan_limit = st.sidebar.slider("എത്ര സ്റ്റോക്കുകൾ സ്കാൻ ചെയ്യണം?", 5, len(stock_list), min(50, len(stock_list)))

    if st.button("🚀 സ്കാനിംഗ് തുടങ്ങാം", use_container_width=True):
        results = []
        bar = st.progress(0)
        status_text = st.empty()
        
        for i, t in enumerate(stock_list[:scan_limit]):
            status_text.text(f"പരിശോധിക്കുന്നു: {t} ({i+1}/{scan_limit})")
            res = analyze_stock(t, fast_n, slow_n, rsi_n)
            if res:
                results.append(res)
            bar.progress((i + 1) / scan_limit)
        
        status_text.empty()
        
        if results:
            st.success(f"കണ്ടീഷനുമായി ചേരുന്ന {len(results)} സ്റ്റോക്കുകൾ കണ്ടെത്തി.")
            df_final = pd.DataFrame(results)
            st.table(df_final)
            
            csv = df_final.to_csv(index=False).encode('utf-8')
            st.download_button("📥 ഡൗൺലോഡ് റിപ്പോർട്ട്", csv, "screener_result.csv", "text/csv")
        else:
            st.warning("ഈ കണ്ടീഷനിൽ സ്റ്റോക്കുകളൊന്നും ഇപ്പോൾ ലഭ്യമല്ല.")

if __name__ == "__main__":
    main()
