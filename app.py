import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- 1. പേജ് സെറ്റപ്പ് ---
st.set_page_config(page_title="Habeeb's Pro Analyzer V3", layout="wide")

# --- 2. ഇൻഡക്സുകൾ ലൈവ് ആയി ലോഡ് ചെയ്യുന്ന ഫംഗ്‌ഷൻ ---
@st.cache_data(ttl=86400)
def get_index_stocks(index_name):
    indices = {
        "Nifty 50": "https://raw.githubusercontent.com/anirban-s/nifty-indices-csv/master/nifty50.csv",
        "Nifty Next 50": "https://raw.githubusercontent.com/anirban-s/nifty-indices-csv/master/niftynext50.csv",
        "Nifty 100": "https://raw.githubusercontent.com/anirban-s/nifty-indices-csv/master/nifty100.csv",
        "Nifty 500": "https://raw.githubusercontent.com/anirban-s/nifty-indices-csv/master/nifty500.csv",
        "Nifty Bank": "https://raw.githubusercontent.com/anirban-s/nifty-indices-csv/master/niftybank.csv",
        "Nifty IT": "https://raw.githubusercontent.com/anirban-s/nifty-indices-csv/master/niftyit.csv"
    }
    try:
        url = indices.get(index_name)
        if url:
            df = pd.read_csv(url)
            col = 'Symbol' if 'Symbol' in df.columns else df.columns[0]
            return df[col].str.strip().tolist()
        return []
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
def analyze_stock(ticker, f_ema, s_ema, rsi_min):
    try:
        yf_ticker = str(ticker).strip() + ".NS"
        df = yf.download(yf_ticker, period="1y", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < s_ema: return None
        
        # Weekly Trend Check
        df_w = yf.download(yf_ticker, period="2y", interval="1wk", progress=False, auto_adjust=True)
        if df_w.empty: return None
        w_ema = df_w['Close'].ewm(span=30, adjust=False).mean().iloc[-1]
        is_weekly_bullish = df_w['Close'].iloc[-1] > w_ema

        ema_f, ema_s, rsi = calculate_indicators(df, f_ema, s_ema)
        curr_price = float(df['Close'].iloc[-1])
        c_rsi = float(rsi.iloc[-1])
        
        # Volume & Breakout
        curr_vol = float(df['Volume'].iloc[-1])
        avg_vol = float(df['Volume'].iloc[-21:-1].mean())
        recent_high = float(df['High'].iloc[-21:-1].max())

        signal = "WAIT"
        if (curr_price > recent_high and curr_price > ema_f.iloc[-1] and 
            ema_f.iloc[-1] > ema_s.iloc[-1] and c_rsi > rsi_min and 
            curr_vol > avg_vol and is_weekly_bullish):
            signal = "🚀 SMART BUY"
        elif curr_price > ema_f.iloc[-1] and ema_f.iloc[-1] > ema_s.iloc[-1] and c_rsi > rsi_min:
            signal = "✅ BUY"
        elif curr_price < ema_s.iloc[-1]:
            signal = "⚠️ EXIT"
            
        if signal == "WAIT": return None

        return {
            "Ticker": ticker,
            "Price": round(curr_price, 2),
            "Signal": signal,
            "RSI": round(c_rsi, 1),
            "Vol Ratio": round(curr_vol/avg_vol, 2) if avg_vol > 0 else 0,
            "W-Trend": "Bullish" if is_weekly_bullish else "Neutral"
        }
    except: return None

# --- 5. മെയിൻ ഇന്റർഫേസ് ---
def main():
    st.title("📈 Habeeb's Pro Analyzer V3")
    
    index_name = st.selectbox("സ്കാൻ ചെയ്യേണ്ട ഇൻഡക്സ് തിരഞ്ഞെടുക്കുക:", 
                             ["Nifty 50", "Nifty Next 50", "Nifty 100", "Nifty 500", "Nifty Bank", "Nifty IT"])
    
    stock_list = get_index_stocks(index_name)

    st.sidebar.header("⚙️ Settings")
    f_n = st.sidebar.number_input("Fast EMA", value=50)
    s_n = st.sidebar.number_input("Slow EMA", value=200)
    rsi_val = st.sidebar.slider("Min RSI", 30, 80, 45)
    
    if not stock_list:
        st.error("ഇൻഡക്സ് ലിസ്റ്റ് ലോഡ് ചെയ്യാൻ കഴിഞ്ഞില്ല!")
        return

    # --- ഇവിടെയാണ് 500 സ്റ്റോക്ക് സെറ്റ് ചെയ്യുന്നത് ---
    max_limit = len(stock_list)
    # default ആയി 50 എണ്ണം സെറ്റ് ചെയ്തിരിക്കുന്നു, നിങ്ങൾക്ക് സ്ലൈഡർ നീക്കി 500 ആക്കാം
    scan_limit = st.sidebar.slider("എത്ര സ്റ്റോക്കുകൾ സ്കാൻ ചെയ്യണം?", 1, max_limit, max_limit)

    if st.button("🚀 Start Scanning", use_container_width=True):
        results = []
        bar = st.progress(0)
        status = st.empty()
        
        for i, ticker in enumerate(stock_list[:scan_limit]):
            status.text(f"Scanning {index_name}: {ticker} ({i+1}/{scan_limit})")
            res = analyze_stock(ticker, f_n, s_n, rsi_val)
            if res: results.append(res)
            bar.progress((i + 1) / scan_limit)
        
        status.empty()
        if results:
            df_final = pd.DataFrame(results).sort_values(by="Signal", ascending=False)
            st.success(f"പൂർത്തിയായി! {len(df_final)} സ്റ്റോക്കുകൾ കണ്ടെത്തി.")
            
            def color_row(val):
                if "SMART" in str(val): return 'background-color: #d4edda; color: #155724; font-weight: bold'
                if "EXIT" in str(val): return 'background-color: #f8d7da; color: #721c24'
                return ''
            
            st.dataframe(df_final.style.map(color_row, subset=['Signal']), use_container_width=True, hide_index=True)
            
            # --- CSV ഡൗൺലോഡ് ബട്ടൺ ---
            st.markdown("---")
            csv = df_final.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 ഡൗൺലോഡ് റിപ്പോർട്ട് (CSV)",
                data=csv,
                file_name=f'habeeb_signals_{index_name.replace(" ", "_")}.csv',
                mime='text/csv',
                use_container_width=True
            )
        else:
            st.warning("നിബന്ധനകൾ ഒത്തുവരുന്ന സ്റ്റോക്കുകൾ ഇപ്പോൾ ലഭ്യമല്ല.")

if __name__ == "__main__":
    main()
