import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- 1. പേജ് സെറ്റപ്പ് ---
st.set_page_config(page_title="Habeeb's Pro Analyzer V3", layout="wide")

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
        # NSE സൈറ്റിൽ നിന്ന് ഡാറ്റ കിട്ടാൻ വൈകിയാൽ ഉപയോഗിക്കാനുള്ള ബാക്കപ്പ് ലിസ്റ്റ്
        return ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "TATASTEEL", "SBI"]

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

# --- 4. അനാലിസിസ് ലോജിക് (Toggles സെറ്റ് ചെയ്തത്) ---
def analyze_stock(ticker, f_ema, s_ema, rsi_min, smart_buy_on, vol_filter_on):
    try:
        yf_ticker = str(ticker).strip() + ".NS"
        df = yf.download(yf_ticker, period="1y", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < s_ema: return None
        
        # Weekly Bullish Check (Price > 30 Weekly EMA)
        df_w = df.resample('W').last()
        w_ema = df_w['Close'].ewm(span=30, adjust=False).mean().iloc[-1]
        is_weekly_bullish = df_w['Close'].iloc[-1] > w_ema

        ema_f, ema_s, rsi = calculate_indicators(df, f_ema, s_ema)
        curr_price = float(df['Close'].iloc[-1])
        c_rsi = float(rsi.iloc[-1])
        
        curr_vol = float(df['Volume'].iloc[-1])
        avg_vol = float(df['Volume'].iloc[-21:-1].mean())
        vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 0
        recent_high = float(df['High'].iloc[-21:-1].max())

        # വോളിയം കണ്ടീഷൻ സ്വിച്ചിന് അനുസരിച്ച് മാറ്റുന്നു
        vol_check = vol_ratio > 1.5 if vol_filter_on else True

        signal = "WAIT"
        
        # 🚀 SMART BUY: breakout + EMA crossover + RSI + Volume + Weekly Bullish
        if smart_buy_on and (curr_price > recent_high and curr_price > ema_f.iloc[-1] and 
            ema_f.iloc[-1] > ema_s.iloc[-1] and c_rsi > rsi_min and 
            vol_check and is_weekly_bullish):
            signal = "🚀 SMART BUY"
            
        # ✅ BUY: Standard technical setup
        elif curr_price > ema_f.iloc[-1] and ema_f.iloc[-1] > ema_s.iloc[-1] and c_rsi > rsi_min and vol_check:
            signal = "✅ BUY"
            
        # ⚠️ EXIT
        elif curr_price < ema_s.iloc[-1]:
            signal = "⚠️ EXIT"
            
        if signal == "WAIT": return None
        
        return {
            "Ticker": ticker, 
            "Price": round(curr_price, 2), 
            "Signal": signal,
            "RSI": round(c_rsi, 1), 
            "Vol Ratio": round(vol_ratio, 2),
            "W-Trend": "Bullish" if is_weekly_bullish else "Neutral"
        }
    except: return None

# --- 5. മെയിൻ ഇന്റർഫേസ് ---
def main():
    st.title("📈 Habeeb's Pro Analyzer V3")
    
    index_name = st.selectbox("ഇൻഡക്സ് തിരഞ്ഞെടുക്കുക:", 
                             ["Nifty 50", "Nifty Next 50", "Nifty 100", "Nifty 500", "Nifty Bank", "Nifty IT"])
    
    stock_list = get_index_stocks(index_name)

    st.sidebar.header("⚙️ Settings")
    f_n = st.sidebar.number_input("Fast EMA", value=50)
    s_n = st.sidebar.number_input("Slow EMA", value=200)
    rsi_val = st.sidebar.slider("Min RSI", 30, 80, 45)
    
    st.sidebar.markdown("---")
    # ഓൺ/ഓഫ് സ്വിച്ചുകൾ
    smart_buy_toggle = st.sidebar.checkbox("Enable 🚀 SMART BUY", value=True)
    vol_filter_toggle = st.sidebar.checkbox("Enable Volume Filter", value=True, help="ഓഫ് ചെയ്താൽ വോളിയം കുറഞ്ഞ സ്റ്റോക്കുകളും സിഗ്നലിൽ വരും.")

    if not stock_list:
        st.error("Error: സ്റ്റോക്ക് ലിസ്റ്റ് ലോഡ് ചെയ്യാൻ സാധിച്ചില്ല.")
        return

    total_stocks = len(stock_list)
    st.info(f"തിരഞ്ഞെടുത്ത ഇൻഡക്സിൽ {total_stocks} സ്റ്റോക്കുകൾ ഉണ്ട്.")

    if st.button(f"🚀 Start Full Scan", use_container_width=True):
        results = []
        bar = st.progress(0)
        status = st.empty()
        res_table = st.empty() 
        
        for i, ticker in enumerate(stock_list):
            status.text(f"Scanning {i+1}/{total_stocks}: {ticker}")
            # സിഗ്നൽ ലഭിക്കുമ്പോൾ പുതിയ ടോഗിൾ വാല്യൂസും ഫംഗ്‌ഷനിലേക്ക് അയക്കുന്നു
            res = analyze_stock(ticker, f_n, s_n, rsi_val, smart_buy_toggle, vol_filter_toggle)
            if res: 
                results.append(res)
                # സിഗ്നലുകൾ തത്സമയം ടേബിളിൽ അപ്‌ഡേറ്റ് ചെയ്യുന്നു
                df_display = pd.DataFrame(results).sort_values(by="Signal", ascending=False)
                res_table.dataframe(df_display, use_container_width=True, hide_index=True)
            
            bar.progress((i + 1) / total_stocks)
        
        status.text("✅ സ്കാനിംഗ് പൂർത്തിയായി!")
        
        if results:
            st.success(f"ആകെ {len(results)} സ്റ്റോക്കുകൾ കണ്ടെത്തി.")
            csv = pd.DataFrame(results).to_csv(index=False).encode('utf-8')
            st.download_button(label="📥 റിപ്പോർട്ട് ഡൗൺലോഡ് (CSV)", data=csv,
                               file_name=f'habeeb_scan_{index_name}.csv', mime='text/csv', use_container_width=True)
        else:
            st.warning("നിബന്ധനകൾക്ക് അനുയോജ്യമായ സ്റ്റോക്കുകൾ ഇപ്പോൾ ലഭ്യമല്ല.")

if __name__ == "__main__":
    main()
