import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- 1. പേജ് സെറ്റപ്പ് ---
st.set_page_config(page_title="Habeeb's Trading Dashboard Pro", layout="wide")

@st.cache_data
def load_stock_list():
    try:
        df = pd.read_csv("nifty_list.csv")
        df.columns = df.columns.str.strip().str.upper()
        if 'TICKER' in df.columns:
            return df['TICKER'].dropna().str.strip().unique().tolist()
        return []
    except:
        st.error("nifty_list.csv ഫയൽ കണ്ടെത്തിയില്ല.")
        return []

# --- 2. ഇൻഡിക്കേറ്റർ കാൽക്കുലേഷൻ ---
def calculate_indicators(df, f_period, s_period):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    close = df['Close'].astype(float)
    
    # EMAs
    ema_f = close.ewm(span=f_period, adjust=False).mean()
    ema_s = close.ewm(span=s_period, adjust=False).mean()
    
    # RSI
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return ema_f, ema_s, rsi.fillna(50)

# --- 3. അഡ്വാൻസ്ഡ് അനാലിസിസ് ---
def analyze_stock(ticker, f_ema, s_ema, rsi_min):
    try:
        clean_ticker = str(ticker).replace("NSE:", "").strip()
        yf_ticker = clean_ticker + ".NS"
        
        # Daily Data (1 വർഷത്തെ ഡാറ്റ)
        df = yf.download(yf_ticker, period="1y", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < s_ema: return None
        
        # Weekly Trend (2 വർഷത്തെ വീക്ക്‌ലി ഡാറ്റ)
        df_w = yf.download(yf_ticker, period="2y", interval="1wk", progress=False, auto_adjust=True)
        w_ema = df_w['Close'].ewm(span=30, adjust=False).mean().iloc[-1]
        w_trend = "⬆️ BULL" if df_w['Close'].iloc[-1] > w_ema else "⬇️ BEAR"

        df = df.dropna()
        ema_f_series, ema_s_series, rsi_series = calculate_indicators(df, f_ema, s_ema)
        
        curr_price = float(df['Close'].iloc[-1])
        c_rsi = float(rsi_series.iloc[-1])
        c_ema_f = float(ema_f_series.iloc[-1])
        c_ema_s = float(ema_s_series.iloc[-1])
        
        # Volume & Breakout logic
        curr_vol = float(df['Volume'].iloc[-1])
        avg_vol = float(df['Volume'].iloc[-21:-1].mean())
        vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 0
        recent_high = float(df['High'].iloc[-21:-1].max())
        
        signal = "WAIT"
        if curr_price > recent_high and c_ema_f > c_ema_s and c_rsi > rsi_min and vol_ratio > 1.2:
            signal = "🚀 STRONG BUY"
        elif curr_price > c_ema_f and c_ema_f > c_ema_s:
            signal = "✅ BULLISH"
        elif curr_price < c_ema_s:
            signal = "⚠️ EXIT"
            
        if signal == "WAIT": return None

        # Target & SL
        sl = round(c_ema_s * 0.98, 1)
        target = round(curr_price * 1.10, 1)
        tv_link = f"https://www.tradingview.com/chart/?symbol=NSE:{clean_ticker}"

        return {
            "Ticker": ticker,
            "Price": round(curr_price, 2),
            "Signal": signal,
            "W-Trend": w_trend,
            "RSI": round(c_rsi, 1),
            "Vol Ratio": round(vol_ratio, 2),
            "Target": target,
            "StopLoss": sl,
            "Chart": tv_link
        }
    except:
        return None

# --- 4. മെയിൻ ഇന്റർഫേസ് ---
def main():
    st.title("📈 Habeeb's Pro Analyzer V3 (Verified)")
    st.markdown("---")
    
    # Sidebar
    st.sidebar.header("⚙️ Settings")
    f_n = st.sidebar.number_input("Fast EMA", value=50)
    s_n = st.sidebar.number_input("Slow EMA", value=200)
    rsi_val = st.sidebar.slider("Min RSI Limit", 30, 80, 60)
    
    stock_list = load_stock_list()
    if not stock_list: return
    scan_limit = st.sidebar.slider("Stocks to Scan", 5, len(stock_list), 50)

    if st.button("🚀 Start Scanning", use_container_width=True):
        results = []
        bar = st.progress(0)
        status = st.empty()
        
        for i, t in enumerate(stock_list[:scan_limit]):
            status.text(f"Scanning: {t} ({i+1}/{scan_limit})")
            res = analyze_stock(t, f_n, s_n, rsi_val)
            if res: results.append(res)
            bar.progress((i + 1) / scan_limit)
        
        status.empty()
        
        if results:
            df_final = pd.DataFrame(results)
            st.success(f"പൂർത്തിയായി! {len(df_final)} സിഗ്നലുകൾ കണ്ടെത്തി.")
            
            # കളർ ഹൈലൈറ്റിംഗ് ഫംഗ്‌ഷൻ
            def highlight_signal(row):
                if 'STRONG' in str(row.Signal): return ['background-color: #d4edda'] * len(row)
                if 'EXIT' in str(row.Signal): return ['background-color: #f8d7da'] * len(row)
                return [''] * len(row)

            # ഡിസ്‌പ്ലേ
            st.dataframe(
                df_final.style.apply(highlight_signal, axis=1),
                column_config={
                    "Chart": st.column_config.LinkColumn("Chart Link", display_text="Open Chart")
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("നിബന്ധനകൾ ഒത്തുവരുന്ന സ്റ്റോക്കുകൾ ഇപ്പോൾ ലഭ്യമല്ല.")

if __name__ == "__main__":
    main()
