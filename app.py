import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import date

# --- 1. പേജ് സെറ്റപ്പ് ---
st.set_page_config(page_title="Habeeb's Pro Analyzer V12", layout="wide")

# --- 2. സെഷൻ സ്റ്റേറ്റ് (ഡാറ്റ നിലനിർത്താൻ) ---
if 'portfolio_df' not in st.session_state:
    st.session_state.portfolio_df = pd.DataFrame(columns=['Ticker', 'Buy Date', 'Qty', 'Avg Price'])

# --- 3. ഇൻഡിക്കേറ്റർ & സിഗ്നൽ ലോജിക് ---
def analyze_stock(ticker, f_p, s_p):
    try:
        yf_ticker = str(ticker).strip() + ".NS"
        # 1 year data download
        df = yf.download(yf_ticker, period="1y", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < s_p: return None
        
        close = df['Close'].astype(float)
        ema_f = close.ewm(span=f_p, adjust=False).mean().iloc[-1]
        ema_s = close.ewm(span=s_p, adjust=False).mean().iloc[-1]
        curr_price = float(close.iloc[-1])
        
        # സിഗ്നൽ ലോജിക്
        if curr_price > ema_f and ema_f > ema_s:
            sig = "✅ BUY"
        elif curr_price < ema_s:
            sig = "⚠️ EXIT"
        else:
            sig = "⏳ WAIT"
            
        return {"LTP": round(curr_price, 2), "Signal": sig}
    except: return None

# --- 4. മെയിൻ ഇന്റർഫേസ് ---
def main():
    st.title("📈 Habeeb's Pro Analyzer V12")

    tab1, tab2, tab3 = st.tabs(["🔍 Market & Add", "💰 Portfolio P&L", "📂 Data Manager"])

    # Sidebar Settings
    st.sidebar.header("⚙️ Settings")
    f_p = st.sidebar.number_input("Fast EMA", value=50)
    s_p = st.sidebar.number_input("Slow EMA", value=200)

    # --- TAB 1: ADD STOCKS ---
    with tab1:
        st.subheader("പുതിയ സ്റ്റോക്ക് ചേർക്കുക")
        c1, c2, c3, c4 = st.columns(4)
        t_name = c1.text_input("Ticker (e.g. TCS)").upper()
        t_date = c2.date_input("Purchase Date", date.today())
        t_qty = c3.number_input("Qty", min_value=1, value=1)
        t_price = c4.number_input("Avg Price", min_value=0.1, value=100.0)
        
        if st.button("➕ Add to Portfolio", use_container_width=True):
            if t_name:
                new_row = pd.DataFrame([[t_name, t_date, t_qty, t_price]], 
                                       columns=['Ticker', 'Buy Date', 'Qty', 'Avg Price'])
                st.session_state.portfolio_df = pd.concat([st.session_state.portfolio_df, new_row]).reset_index(drop=True)
                st.success(f"{t_name} ആഡ് ചെയ്തു!")

    # --- TAB 2: PORTFOLIO P&L ---
    with tab2:
        if not st.session_state.portfolio_df.empty:
            st.subheader("നിങ്ങളുടെ പോർട്ട്‌ഫോളിയോ നില")
            results = []
            total_inv = 0
            total_cur = 0
            
            bar = st.progress(0)
            df = st.session_state.portfolio_df
            
            for idx, row in df.iterrows():
                analysis = analyze_stock(row['Ticker'], f_p, s_p)
                if analysis:
                    ltp = analysis['LTP']
                    inv = row['Qty'] * row['Avg Price']
                    cur = row['Qty'] * ltp
                    pnl = cur - inv
                    pnl_pct = (pnl/inv)*100 if inv > 0 else 0
                    
                    total_inv += inv
                    total_cur += cur
                    
                    results.append({
                        "Ticker": row['Ticker'],
                        "Buy Date": row['Buy Date'],
                        "Qty": row['Qty'],
                        "Avg Price": row['Avg Price'],
                        "LTP": ltp,
                        "Invested": round(inv, 2),
                        "P&L": round(pnl, 2),
                        "P&L %": f"{round(pnl_pct, 2)}%",
                        "Signal": analysis['Signal']
                    })
                bar.progress((idx + 1) / len(df))
            
            # ടേബിൾ ഡിസ്‌പ്ലേ
            res_df = pd.DataFrame(results)
            res_df.insert(0, 'Sl No', range(1, len(res_df) + 1))
            st.dataframe(res_df, use_container_width=True, hide_index=True)

            # Summary Metrics
            st.divider()
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Invested", f"₹{round(total_inv, 2)}")
            m2.metric("Current Value", f"₹{round(total_cur, 2)}", delta=f"{round(total_cur - total_inv, 2)}")
            m3.metric("Net Profit %", f"{round(((total_cur-total_inv)/total_inv)*100, 2) if total_inv > 0 else 0}%")

            # Remove Stock Option
            st.divider()
            del_tkr = st.selectbox("ഒഴിവാക്കേണ്ട സ്റ്റോക്ക് തിരഞ്ഞെടുക്കുക:", ["None"] + list(df['Ticker'].unique()))
            if st.button("🗑️ Remove Selected Stock") and del_tkr != "None":
                st.session_state.portfolio_df = df[df['Ticker'] != del_tkr].reset_index(drop=True)
                st.rerun()
        else:
            st.info("പോർട്ട്‌ഫോളിയോയിൽ ഡാറ്റയില്ല. 'Market & Add' ടാബിൽ പോയി ആഡ് ചെയ്യുക.")

    # --- TAB 3: DATA MANAGER ---
    with tab3:
        st.subheader("ഫയലുകൾ കൈകാര്യം ചെയ്യുക")
        
        # Sample Template Download
        sample_df = pd.DataFrame([['RELIANCE', '2024-01-01', 10, 2500.0]], 
                                 columns=['Ticker', 'Buy Date', 'Qty', 'Avg Price'])
        st.download_button("📥 Download Sample CSV Template", 
                           sample_df.to_csv(index=False).encode('utf-8'), 
                           "sample_portfolio.csv", "text/csv")
        
        st.divider()
        
        # Upload CSV
        up_file = st.file_uploader("നിങ്ങളുടെ സേവ് ചെയ്ത CSV ഫയൽ അപ്‌ലോഡ് ചെയ്യുക", type=["csv"])
        if up_file:
            up_df = pd.read_csv(up_file)
            # തീയതി ഫോർമാറ്റ് ശരിയാക്കുന്നു
            if 'Buy Date' in up_df.columns:
                up_df['Buy Date'] = pd.to_datetime(up_df['Buy Date']).dt.date
            
            st.session_state.portfolio_df = pd.concat([st.session_state.portfolio_df, up_df]).drop_duplicates().reset_index(drop=True)
            st.success("ഫയൽ ലോഡ് ചെയ്തു! Portfolio P&L ടാബിൽ പോയി നോക്കുക.")

        st.divider()

        # Save/Export Data
        if not st.session_state.portfolio_df.empty:
            st.download_button("💾 Save Current Portfolio (CSV)", 
                               st.session_state.portfolio_df.to_csv(index=False).encode('utf-8'), 
                               f"portfolio_{date.today()}.csv", "text/csv")
        
        if st.button("🚨 Clear All Data"):
            st.session_state.portfolio_df = pd.DataFrame(columns=['Ticker', 'Buy Date', 'Qty', 'Avg Price'])
            st.rerun()

if __name__ == "__main__":
    main()
