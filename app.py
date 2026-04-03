import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import date

# --- 1. പേജ് സെറ്റപ്പ് ---
st.set_page_config(page_title="Habeeb's Pro Analyzer V16", layout="wide")

# --- 2. സെഷൻ സ്റ്റേറ്റ് (ഡാറ്റ നിലനിർത്താൻ) ---
if 'portfolio_df' not in st.session_state:
    st.session_state.portfolio_df = pd.DataFrame(columns=['Ticker', 'Buy Date', 'Qty', 'Avg Price'])
if 'sales_df' not in st.session_state:
    st.session_state.sales_df = pd.DataFrame(columns=['Ticker', 'Sell Date', 'Qty', 'Sell Price', 'Profit/Loss'])

# --- 3. ഇൻഡക്സുകൾ ലോഡ് ചെയ്യുന്ന ഫംഗ്‌ഷൻ ---
@st.cache_data(ttl=86400)
def get_index_stocks(index_name):
    indices = {
        "Nifty 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        "Nifty Next 50": "https://archives.nseindia.com/content/indices/ind_niftynext50list.csv",
        "Nifty 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    }
    try:
        url = indices.get(index_name)
        df = pd.read_csv(url)
        col = 'Symbol' if 'Symbol' in df.columns else df.columns[0]
        return df[col].str.strip().tolist()
    except:
        return ["RELIANCE", "TCS", "HDFCBANK", "INFY"]

# --- 4. അനാലിസിസ് ലോജിക് ---
def analyze_stock(ticker, f_p, s_p, rsi_val):
    try:
        yf_ticker = str(ticker).strip() + ".NS"
        df = yf.download(yf_ticker, period="1y", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < s_p: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        close = df['Close'].astype(float)
        ema_f = close.ewm(span=f_p, adjust=False).mean()
        ema_s = close.ewm(span=s_p, adjust=False).mean()
        
        delta = close.diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-1 * delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rsi = 100 - (100 / (1 + (gain / loss.replace(0, np.nan))))
        
        curr_price = float(close.iloc[-1])
        curr_rsi = float(rsi.iloc[-1])
        
        if curr_price > ema_f.iloc[-1] and ema_f.iloc[-1] > ema_s.iloc[-1] and curr_rsi > rsi_val:
            sig = "✅ BUY"
        elif curr_price < ema_s.iloc[-1]:
            sig = "⚠️ EXIT"
        else:
            sig = "⏳ WAIT"
            
        return {"LTP": round(curr_price, 2), "RSI": round(curr_rsi, 1), "Signal": sig}
    except: return None

# --- 5. മെയിൻ ഇന്റർഫേസ് ---
def main():
    st.title("📈 Habeeb's Pro Analyzer V16")
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🔍 Scan", "➕ Add", "🤝 Sell", "💰 Portfolio", "📂 Data"])

    st.sidebar.header("⚙️ Settings")
    f_p = st.sidebar.number_input("Fast EMA", value=50)
    s_p = st.sidebar.number_input("Slow EMA", value=200)
    rsi_v = st.sidebar.slider("Min RSI", 20, 80, 45)

    # TAB 1: SCAN
    with tab1:
        idx_choice = st.selectbox("Select Index", ["Nifty 50", "Nifty Next 50", "Nifty 500"])
        stock_list = get_index_stocks(idx_choice)
        if st.button(f"Scan {len(stock_list)} Stocks"):
            results = []
            bar = st.progress(0)
            table = st.empty()
            for i, tkr in enumerate(stock_list):
                res = analyze_stock(tkr, f_p, s_p, rsi_v)
                if res:
                    res['Ticker'] = tkr
                    results.append(res)
                    table.dataframe(pd.DataFrame(results), use_container_width=True)
                bar.progress((i+1)/len(stock_list))

    # TAB 2: ADD
    with tab2:
        c1, c2, c3, c4 = st.columns(4)
        t_n = c1.text_input("Ticker").upper()
        t_d = c2.date_input("Buy Date", date.today())
        t_q = c3.number_input("Qty", min_value=1, key="add_qty")
        t_p = c4.number_input("Price", min_value=0.1, key="add_prc")
        if st.button("Save Buy"):
            new = pd.DataFrame([[t_n, t_d, t_q, t_p]], columns=['Ticker', 'Buy Date', 'Qty', 'Avg Price'])
            st.session_state.portfolio_df = pd.concat([st.session_state.portfolio_df, new]).reset_index(drop=True)
            st.success("Added!")

    # TAB 3: SELL (New Feature)
    with tab3:
        st.subheader("Sell Your Stock")
        if not st.session_state.portfolio_df.empty:
            df_p = st.session_state.portfolio_df
            sel_tkr = st.selectbox("വിറ്റ സ്റ്റോക്ക് ഏതാണ്?", df_p['Ticker'].unique())
            
            # കണ്ടുപിടിക്കുന്നു (Current Data)
            stock_info = df_p[df_p['Ticker'] == sel_tkr].iloc[0]
            
            c1, c2, c3 = st.columns(3)
            s_date = c1.date_input("Sell Date", date.today())
            s_qty = c2.number_input("Sell Qty", min_value=1, max_value=int(stock_info['Qty']))
            s_price = c3.number_input("Sell Price", min_value=0.1)
            
            if st.button("Confirm Sell"):
                buy_price = stock_info['Avg Price']
                profit = (s_price - buy_price) * s_qty
                
                # Sales ലോഗിലേക്ക് മാറ്റുന്നു
                new_sale = pd.DataFrame([[sel_tkr, s_date, s_qty, s_price, profit]], 
                                        columns=['Ticker', 'Sell Date', 'Qty', 'Sell Price', 'Profit/Loss'])
                st.session_state.sales_df = pd.concat([st.session_state.sales_df, new_sale]).reset_index(drop=True)
                
                # പോർട്ട്‌ഫോളിയോയിൽ നിന്ന് ക്വാണ്ടിറ്റി കുറയ്ക്കുന്നു
                if s_qty == stock_info['Qty']:
                    st.session_state.portfolio_df = df_p[df_p['Ticker'] != sel_tkr].reset_index(drop=True)
                else:
                    st.session_state.portfolio_df.loc[df_p['Ticker'] == sel_tkr, 'Qty'] -= s_qty
                
                st.success(f"Sold! Profit/Loss: ₹{round(profit, 2)}")
                st.rerun()
        else:
            st.info("വിൽക്കാൻ സ്റ്റോക്കുകൾ ഒന്നുമില്ല.")

    # TAB 4: PORTFOLIO & SALES REPORT
    with tab4:
        st.subheader("Current Portfolio")
        st.dataframe(st.session_state.portfolio_df, use_container_width=True)
        
        st.divider()
        st.subheader("Realized Profit/Loss (വിറ്റ സ്റ്റോക്കുകൾ)")
        if not st.session_state.sales_df.empty:
            st.dataframe(st.session_state.sales_df, use_container_width=True)
            st.metric("Total Realized Profit", f"₹{round(st.session_state.sales_df['Profit/Loss'].sum(), 2)}")
        else:
            st.write("വിൽപന ഒന്നും നടന്നിട്ടില്ല.")

    # TAB 5: DATA
    with tab5:
        st.download_button("Download Portfolio", st.session_state.portfolio_df.to_csv(index=False).encode('utf-8'), "port.csv")
        st.download_button("Download Sales Report", st.session_state.sales_df.to_csv(index=False).encode('utf-8'), "sales.csv")

if __name__ == "__main__":
    main()
