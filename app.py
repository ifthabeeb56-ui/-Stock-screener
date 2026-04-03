import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- 1. പേജ് സെറ്റപ്പ് ---
st.set_page_config(page_title="Habeeb's Power Screener Pro", layout="wide")

@st.cache_data
def load_stock_list():
    try:
        df = pd.read_csv("nifty_list.csv")
        df.columns = df.columns.str.strip().str.upper()
        if 'TICKER' in df.columns:
            return df['TICKER'].dropna().str.strip().unique().tolist()
        else:
            st.error("CSV ഫയലിൽ 'Ticker' എന്ന കോളം കണ്ടെത്തിയില്ല.")
            return []
    except Exception as e:
        st.error(f"Error loading CSV: {e}")
        return []

# --- 2. ഇൻഡിക്കേറ്റർ കാൽക്കുലേഷൻ ---
def calculate_custom_indicators(df, f_period, s_period):
    # yfinance പുതിയ വേർഷനിലെ MultiIndex പ്രശ്നം ഒഴിവാക്കാൻ
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    # ഡാറ്റ ഉണ്ടെന്ന് ഉറപ്പാക്കുന്നു
    if 'Close' not in df.columns:
        return None, None, None

    close = df['Close'].astype(float)
    
    # EMAs
    ema_f = close.ewm(span=f_period, adjust=False).mean()
    ema_s = close.ewm(span=s_period, adjust=False).mean()
    
    # RSI (Wilder's Smoothing)
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    
    return ema_f, ema_s, rsi.fillna(50)

# --- 3. സ്റ്റോക്ക് അനാലിസിസ് ---
def analyze_stock(ticker, f_ema, s_ema, rsi_min):
    try:
        clean_ticker = str(ticker).replace("NSE:", "").strip() + ".NS"
        
        # ഡാറ്റ ഡൗൺലോഡ് (auto_adjust ഉപയോഗിച്ച് ഡിവിഡന്റ് അഡ്ജസ്റ്റ് ചെയ്യുന്നു)
        df = yf.download(clean_ticker, period="1y", interval="1d", progress=False, auto_adjust=True)
        
        if df.empty or len(df) < s_ema:
            return None
        
        df = df.dropna()
        ema_f, ema_s, rsi = calculate_custom_indicators(df, f_ema, s_ema)
        
        if ema_f is None: return None

        curr_price = float(df['Close'].iloc[-1])
        c_ema_f = float(ema_f.iloc[-1])
        c_ema_s = float(ema_s.iloc[-1])
        c_rsi = float(rsi.iloc[-1])

        # 20 Day Breakout: കഴിഞ്ഞ 20 ദിവസത്തെ ഏറ്റവും ഉയർന്ന ഹൈ
        recent_high = float(df['High'].iloc[-21:-1].max())
        
        # സിഗ്നൽ തീരുമാനിക്കുന്നു
        if curr_price > recent_high and c_ema_f > c_ema_s and c_rsi > rsi_min:
            signal = "🚀 STRONG BUY"
        elif curr_price > c_ema_f and c_ema_f > c_ema_s:
            signal = "✅ BULLISH"
        elif curr_price < c_ema_s:
            signal = "⚠️ EXIT"
        else:
            signal = "⏳ WAIT"

        return {
            "Ticker": ticker,
            "Price": round(curr_price, 2),
            "Signal": signal,
            "RSI": round(c_rsi, 1),
            f"EMA {f_ema}": round(c_ema_f, 1),
            "20D High": round(recent_high, 2)
        }
    except:
        return None

# --- 4. മെയിൻ ഇന്റർഫേസ് ---
def main():
    st.title("📈 Habeeb's Power Screener (Final Verified)")
    st.info("ഈ സ്കാനർ ട്രെൻഡ് (EMA), മൊമെന്റം (RSI), ബ്രേക്കൗട്ട് (20D High) എന്നിവ ഒരേസമയം പരിശോധിക്കുന്നു.")
    
    # Sidebar Settings
    st.sidebar.header("⚙️ Settings")
    fast_n = st.sidebar.number_input("Fast EMA (ഉദാ: 50)", value=50)
    slow_n = st.sidebar.number_input("Slow EMA (ഉദാ: 200)", value=200)
    rsi_val = st.sidebar.slider("Minimum RSI Limit", 30, 80, 60)
    
    stock_list = load_stock_list()
    if not stock_list: return

    scan_limit = st.sidebar.slider("എത്ര സ്റ്റോക്കുകൾ സ്കാൻ ചെയ്യണം?", 5, len(stock_list), min(100, len(stock_list)))

    if st.button("🚀 Start Scanning", use_container_width=True):
        results = []
        bar = st.progress(0)
        status = st.empty()
        
        for i, t in enumerate(stock_list[:scan_limit]):
            status.text(f"പരിശോധിക്കുന്നു: {t} ({i+1}/{scan_limit})")
            res = analyze_stock(t, fast_n, slow_n, rsi_val)
            if res:
                results.append(res)
            bar.progress((i + 1) / scan_limit)
        
        status.empty()
        
        if results:
            st.success(f"പൂർത്തിയായി! {len(results)} സ്റ്റോക്കുകൾ കണ്ടെത്തി.")
            df_final = pd.DataFrame(results)
            
            # ടേബിൾ കളറിംഗ് ലോജിക്
            def highlight_signal(row):
                if row.Signal == "🚀 STRONG BUY":
                    return ['background-color: #d4edda; color: #155724'] * len(row)
                elif row.Signal == "⚠️ EXIT":
                    return ['background-color: #f8d7da; color: #721c24'] * len(row)
                elif row.Signal == "✅ BULLISH":
                    return ['background-color: #fff3cd; color: #856404'] * len(row)
                return [''] * len(row)

            # സ്റ്റൈൽ ചെയ്ത ടേബിൾ ഡിസ്‌പ്ലേ
            st.dataframe(df_final.style.apply(highlight_signal, axis=1), use_container_width=True)
            
            csv = df_final.to_csv(index=False).encode('utf-8')
            st.download_button("📥 ഡൗൺലോഡ് റിപ്പോർട്ട്", csv, "stock_signals.csv", "text/csv")
        else:
            st.warning("നിബന്ധനകൾ ഒത്തുപോകുന്ന സ്റ്റോക്കുകൾ ഇപ്പോൾ ലഭ്യമല്ല.")

if __name__ == "__main__":
    main()
