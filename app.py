import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time

# --- 1. പേജ് സെറ്റപ്പ് ---
st.set_page_config(page_title="Habeeb's Pro Analyzer V3", layout="wide")

# --- 2. ഇൻഡക്സുകൾ ലോഡ് ചെയ്യുന്ന ഫംഗ്‌ഷൻ ---
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
            # Symbol കോളം കണ്ടുപിടിക്കുന്നു
            col = 'Symbol' if 'Symbol' in df.columns else df.columns[0]
            stocks = df[col].str.strip().tolist()
            return stocks
        return []
    except Exception as e:
        st.sidebar.error(f"Error loading index: {e}")
        return ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"]

# --- 3. ഇൻഡിക്കേറ്റർ കാൽക്കുലേഷൻ ---
def calculate_indicators(df, f_period, s_period):
    # MultiIndex കോളം പ്രശ്നം ഒഴിവാക്കാൻ
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    close = df['Close'].astype(float)
    
    # EMA Calculation
    ema_f = close.ewm(span=f_period, adjust=False).mean()
    ema_s = close.ewm(span=s_period, adjust=False).mean()
    
    # RSI Calculation
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
        # ഒരൊറ്റ തവണ ഡാറ്റ എടുക്കുന്നു (വേഗത കൂട്ടാൻ)
        df = yf.download(yf_ticker, period="2y", interval="1d", progress=False, auto_adjust=True)
        
        if df.empty or len(df) < s_ema:
            return None
        
        # Weekly Trend (Daily-യിൽ നിന്ന് മാറ്റുന്നു)
        df_w = df.resample('W').last()
        w_ema = df_w['Close'].ewm(span=30, adjust=False).mean().iloc[-1]
        is_weekly_bullish = df_w['Close'].iloc[-1] > w_ema

        ema_f, ema_s, rsi = calculate_indicators(df, f_ema, s_ema)
        
        curr_price = float(df['Close'].iloc[-1])
        c_rsi = float(rsi.iloc[-1])
        curr_vol = float(df['Volume'].iloc[-1])
        avg_vol = float(df['Volume'].iloc[-21:-1].mean()) # 20 days avg vol
        recent_high = float(df['High'].iloc[-21:-1].max()) # 20 days high

        signal = "WAIT"
        
        # Logic 1: 🚀 SMART BUY (Breakout + Volume + Weekly Trend)
        if (curr_price > recent_high and curr_price > ema_f.iloc[-1] and 
            ema_f.iloc[-1] > ema_s.iloc[-1] and c_rsi > rsi_min and 
            curr_vol > avg_vol and is_weekly_bullish):
            signal = "🚀 SMART BUY"
            
        # Logic 2: ✅ BUY (Standard Trend)
        elif curr_price > ema_f.iloc[-1] and ema_f.iloc[-1] > ema_s.iloc[-1] and c_rsi > rsi_min:
            signal = "✅ BUY"
            
        # Logic 3: ⚠️ EXIT
        elif curr_price < ema_s.iloc[-1]:
            signal = "⚠️ EXIT"
            
        if signal == "WAIT":
            return None

        return {
            "Ticker": ticker,
            "Price": round(curr_price, 2),
            "Signal": signal,
            "RSI": round(c_rsi, 1),
            "Vol Ratio": round(curr_vol/avg_vol, 2) if avg_vol > 0 else 0,
            "W-Trend": "Bullish" if is_weekly_bullish else "Neutral"
        }
    except:
        return None

# --- 5. മെയിൻ ഇന്റർഫേസ് ---
def main():
    st.title("📈 Habeeb's Pro Analyzer V3")
    
    # ഇൻഡക്സ് തിരഞ്ഞെടുക്കൽ
    index_name = st.selectbox("സ്കാൻ ചെയ്യേണ്ട ഇൻഡക്സ് തിരഞ്ഞെടുക്കുക:", 
                             ["Nifty 50", "Nifty Next 50", "Nifty 100", "Nifty 500", "Nifty Bank", "Nifty IT"])
    
    stock_list = get_index_stocks(index_name)

    # സൈഡ്ബാർ സെറ്റിംഗ്സ്
    st.sidebar.header("⚙️ സ്കാനർ ക്രമീകരണങ്ങൾ")
    f_n = st.sidebar.number_input("Fast EMA (Short Term)", value=50)
    s_n = st.sidebar.number_input("Slow EMA (Long Term)", value=200)
    rsi_val = st.sidebar.slider("Minimum RSI", 30, 80, 45)
    
    if not stock_list:
        st.error("സ്റ്റോക്ക് ലിസ്റ്റ് ലഭ്യമായില്ല. ദയവായി വീണ്ടും ശ്രമിക്കുക.")
        return

    total_stocks = len(stock_list)
    st.info(f"തിരഞ്ഞെടുത്ത ഇൻഡക്സിൽ **{total_stocks}** സ്റ്റോക്കുകൾ ഉണ്ട്. സ്കാൻ ബട്ടൺ അമർത്തുക.")

    # സ്റ്റാർട്ട് ബട്ടൺ
    if st.button(f"🚀 Start Scanning {total_stocks} Stocks", use_container_width=True):
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, ticker in enumerate(stock_list):
            status_text.text(f"Scanning {i+1}/{total_stocks}: {ticker}...")
            res = analyze_stock(ticker, f_n, s_n, rsi_val)
            if res:
                results.append(res)
            
            # പ്രോഗ്രസ് ബാർ അപ്ഡേറ്റ്
            progress_bar.progress((i + 1) / total_stocks)
        
        status_text.empty()
        
        if results:
            df_final = pd.DataFrame(results).sort_values(by="Signal", ascending=False)
            st.success(f"സ്കാനിംഗ് പൂർത്തിയായി! **{len(df_final)}** സ്റ്റോക്കുകൾ കണ്ടെത്തി.")
            
            # ടേബിൾ ഡിസൈൻ
            def apply_style(val):
                if "SMART" in str(val): return 'background-color: #d4edda; color: #155724; font-weight: bold'
                if "EXIT" in str(val): return 'background-color: #f8d7da; color: #721c24'
                return ''
            
            st.dataframe(df_final.style.applymap(apply_style, subset=['Signal']), use_container_width=True, hide_index=True)
            
            # ഡൗൺലോഡ് ഓപ്ഷൻ
            st.markdown("---")
            csv_data = df_final.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 സ്കാൻ റിപ്പോർട്ട് ഡൗൺലോഡ് ചെയ്യുക (CSV)",
                data=csv_data,
                file_name=f'habeeb_scan_{index_name.replace(" ", "_")}.csv',
                mime='text/csv',
                use_container_width=True
            )
        else:
            st.warning("നിങ്ങളുടെ സെറ്റിംഗ്സിന് അനുയോജ്യമായ സ്റ്റോക്കുകൾ ഒന്നും തന്നെ ഇപ്പോൾ കണ്ടെത്തിയില്ല.")

if __name__ == "__main__":
    main()
