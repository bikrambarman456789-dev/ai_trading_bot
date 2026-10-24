import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
from pushbullet import Pushbullet
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, TakeProfitRequest, StopLossRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus

# Page Setup - Pro Neon Theme
st.set_page_config(page_title="Pro Spot Crypto Trading Bot", layout="wide", initial_sidebar_state="expanded")

# --- CUSTOM CSS FOR DARK NEON PURPLE THEME ---
st.markdown("""
<style>
    .stApp {
        background-color: #0b0b10;
        color: #ffffff;
    }
    [data-testid="stSidebar"] {
        background-color: #121218;
        border-right: 1px solid #2b2b3d;
    }
    div[data-testid="stMetric"] {
        background-color: #161622;
        border: 1px solid #2d2d44;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(138, 43, 226, 0.1);
    }
    div[data-testid="stMetric"] label {
        color: #a0a0b0 !important;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #e2e8f0 !important;
    }
    .stButton>button {
        background: linear-gradient(135deg, #7b2cbf 0%, #9d4edd 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 12px 20px;
        font-weight: bold;
        box-shadow: 0 4px 15px rgba(123, 44, 191, 0.4);
        transition: 0.3s;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #9d4edd 0%, #c77dff 100%);
        box-shadow: 0 6px 20px rgba(157, 78, 221, 0.6);
    }
    .spot-badge {
        background-color: #2e1065;
        color: #c77dff;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 13px;
        font-weight: bold;
        border: 1px solid #7b2cbf;
    }
</style>
""", unsafe_allow_html=True)

# Helper function: Pushbullet Mobile Push Notification Sender
def send_mobile_push(token, title, message):
    if token:
        try:
            pb = Pushbullet(token)
            pb.push_note(title, message)
        except Exception as e:
            pass

# Title Header & Refresh Control
head_col1, head_col2 = st.columns([4, 1])

with head_col1:
    st.markdown("<h1 style='color: #c77dff;'>🪙 BTC/USD Ultimate Algo Bot Terminal</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #94a3b8;'>Interactive Charts, Auto-Trader, Direct Mobile Push & Live Portfolio</p>", unsafe_allow_html=True)

with head_col2:
    st.write("")
    st.write("")
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.write("---")

# --- SIDEBAR CONFIGURATION ---
st.sidebar.markdown("<h3 style='color: #c77dff;'>🔑 Alpaca API Config</h3>", unsafe_allow_html=True)
default_api_key = ""      
default_secret_key = ""   

api_key = st.sidebar.text_input("API Key", value=default_api_key, type="password")
secret_key = st.sidebar.text_input("Secret Key", value=default_secret_key, type="password")

st.sidebar.write("---")
st.sidebar.markdown("<h3 style='color: #c77dff;'>📱 Direct Mobile Push Notification</h3>", unsafe_allow_html=True)
pushbullet_token = st.sidebar.text_input("Pushbullet Access Token", type="password", help="Pushbullet settings se milne wala API Access Token")

st.sidebar.write("---")
st.sidebar.markdown("<h3 style='color: #c77dff;'>🤖 Fully Auto-Trader Mode</h3>", unsafe_allow_html=True)
auto_trade_enabled = st.sidebar.checkbox("Enable Fully Auto-Trading", value=False)

st.sidebar.write("---")
st.sidebar.markdown("<h3 style='color: #c77dff;'>⏱️ Timeframe Selection</h3>", unsafe_allow_html=True)
tf_option = st.sidebar.selectbox(
    "Select Chart Time Frame",
    options=["15m (Day Trading)", "1h (Swing Trading)", "1d (Position Trading)"],
    index=0
)

tf_map = {
    "15m (Day Trading)": ("7d", "15m"),
    "1h (Swing Trading)": ("1mo", "1h"),
    "1d (Position Trading)": ("1y", "1d")
}
period, interval = tf_map[tf_option]

st.sidebar.write("---")
st.sidebar.markdown("<h3 style='color: #c77dff;'>🛡️ Position & Risk Sizing</h3>", unsafe_allow_html=True)
capital = st.sidebar.number_input("Trade Capital ($ USD)", value=1000, step=100)

sl_pct = st.sidebar.slider("Stop Loss (%)", min_value=0.5, max_value=5.0, value=1.5, step=0.1)
tp_pct = st.sidebar.slider("Take Profit (%)", min_value=1.0, max_value=10.0, value=3.0, step=0.1)

rr_ratio = tp_pct / sl_pct
st.sidebar.info(f"📊 **Risk-to-Reward Ratio:** 1 : {rr_ratio:.2f}")

# --- MARKET DATA & STRATEGY ANALYSIS ---
@st.cache_data(ttl=15)
def load_data(p, i):
    data = yf.download("BTC-USD", period=p, interval=i)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    data['EMA9'] = data['Close'].ewm(span=9, adjust=False).mean()
    data['EMA21'] = data['Close'].ewm(span=21, adjust=False).mean()
    return data

try:
    data = load_data(period, interval)
    latest_price = float(data['Close'].iloc[-1])
    ema9 = float(data['EMA9'].iloc[-1])
    ema21 = float(data['EMA21'].iloc[-1])
except Exception as e:
    st.error(f"Error loading market data: {e}")
    st.stop()

btc_qty = capital / latest_price
tp_price_buy = latest_price * (1 + (tp_pct / 100))
sl_price_buy = latest_price * (1 - (sl_pct / 100))

# Display Metrics Cards
col1, col2, col3, col4 = st.columns(4)
col1.metric("Live Price (BTC/USD)", f"${latest_price:,.2f}")
col2.metric("Exact Order Quantity", f"{btc_qty:.5f} BTC")
col3.metric("9 EMA (Fast Trend)", f"${ema9:,.2f}")
col4.metric("21 EMA (Slow Trend)", f"${ema21:,.2f}")

st.write("---")

# --- INTERACTIVE CANDLESTICK CHART ---
st.markdown("### 📊 Live TradingView-Style Candlestick Chart")

fig = go.Figure()

# Candlesticks
fig.add_trace(go.Candlestick(
    x=data.index,
    open=data['Open'],
    high=data['High'],
    low=data['Low'],
    close=data['Close'],
    name="BTC/USD Price"
))

# 9 EMA & 21 EMA Lines
fig.add_trace(go.Scatter(x=data.index, y=data['EMA9'], mode='lines', name='9 EMA', line=dict(color='#a855f7', width=2)))
fig.add_trace(go.Scatter(x=data.index, y=data['EMA21'], mode='lines', name='21 EMA', line=dict(color='#f97316', width=2)))

fig.update_layout(
    template="plotly_dark",
    paper_bgcolor="#0b0b10",
    plot_bgcolor="#121218",
    margin=dict(l=20, r=20, t=30, b=20),
    height=450,
    xaxis_rangeslider_visible=False
)

st.plotly_chart(fig, use_container_width=True)

st.write("---")

# Strategy Signal Logic
if ema9 > ema21:
    signal = "BUY"
    st.success(f"🟢 **STRATEGY STATUS: VALID BUY SIGNAL** (9 EMA ${ema9:,.2f} > 21 EMA ${ema21:,.2f})")
else:
    signal = "SELL"
    st.error(f"🔴 **STRATEGY STATUS: BEARISH TREND / NO BUY SIGNAL** (9 EMA ${ema9:,.2f} <= 21 EMA ${ema21:,.2f}) — Spot order locked for safety.")

# --- ORDER EXECUTION PANEL ---
st.markdown("### ⚡ Order Execution Panel")

c1, c2 = st.columns(2)

def execute_spot_buy():
    if not api_key or not secret_key:
        st.error("❌ Action Blocked: API Key aur Secret Key enter karein!")
        return False
    elif signal != "BUY":
        st.error("⛔ ORDER REJECTED: Live market trend bullish nahi hai!")
        return False
    else:
        try:
            client = TradingClient(api_key, secret_key, paper=True)
            order_data = MarketOrderRequest(
                symbol="BTCUSD",
                qty=round(btc_qty, 4),
                side=OrderSide.BUY,
                time_in_force=TimeInForce.GTC,
                take_profit=TakeProfitRequest(limit_price=round(tp_price_buy, 2)),
                stop_loss=StopLossRequest(stop_price=round(sl_price_buy, 2))
            )
            order = client.submit_order(order_data)
            st.balloons()
            st.success(f"✅ Spot BUY Order Placed! Order ID: `{order.id}`")
            
            # Send Direct Mobile Notification
            title = "🚀 SPOT BUY ORDER EXECUTED"
            msg = f"BTC/USD Buy Alert!\nQty: {btc_qty:.5f} BTC\nPrice: ${latest_price:,.2f}\nTP: ${tp_price_buy:,.2f} | SL: ${sl_price_buy:,.2f}"
            send_mobile_push(pushbullet_token, title, msg)
            return True
        except Exception as e:
            st.error(f"❌ Execution Error: {e}")
            return False

with c1:
    st.markdown("#### 🛒 Spot Buy Details")
    st.markdown(f"""
    * **Market Type:** <span class="spot-badge">SPOT (Actual BTC Asset)</span>
    * **Selected Capital:** `${capital:,.2f} USD`
    * **Calculated Qty:** `{btc_qty:.5f} BTC`
    * **Take Profit Target (+{tp_pct}%):** `${tp_price_buy:,.2f}`
    * **Stop Loss Limit (-{sl_pct}%):** `${sl_price_buy:,.2f}`
    """, unsafe_allow_html=True)
    
    st.write("")
    buy_btn_label = f"🚀 Execute Spot Buy ({btc_qty:.5f} BTC)"
    if st.button(buy_btn_label, use_container_width=True):
        execute_spot_buy()

with c2:
    st.markdown("#### 🤖 Fully Auto-Trader Status")
    if auto_trade_enabled:
        st.success("🤖 **AUTO-TRADING IS ACTIVE:** System background mein signals monitor kar raha hai.")
        if signal == "BUY" and api_key and secret_key:
            client = TradingClient(api_key, secret_key, paper=True)
            positions = client.get_all_positions()
            has_btc = any(p.symbol == "BTCUSD" for p in positions)
            if not has_btc:
                st.info("⚡ Auto-Trader triggering BUY order...")
                execute_spot_buy()
    else:
        st.warning("⚙️ Auto-Trader OFF hai. Trade lene ke liye manual button ka use karein ya sidebar se Auto Mode ON karein.")

st.write("---")

# --- LIVE POSITIONS TRACKER ---
st.markdown("### 💼 Live Portfolio & Positions Tracker")

if api_key and secret_key:
    try:
        client = TradingClient(api_key, secret_key, paper=True)
        positions = client.get_all_positions()
        
        if not positions:
            st.info("ℹ️ Abhi koi Open Position nahi hai.")
        else:
            for pos in positions:
                if pos.symbol == "BTCUSD":
                    qty_held = float(pos.qty)
                    avg_entry = float(pos.avg_entry_price)
                    current_val = float(pos.market_value)
                    unrealized_pl = float(pos.unrealized_pl)
                    unrealized_plpc = float(pos.unrealized_plpc) * 100
                    
                    pl_color = "🟢" if unrealized_pl >= 0 else "🔴"
                    
                    st.markdown(f"#### 📊 Active Asset: **{pos.symbol}**")
                    
                    p_col1, p_col2, p_col3, p_col4 = st.columns(4)
                    p_col1.metric("Quantity Held", f"{qty_held:.5f} BTC")
                    p_col2.metric("Avg Entry Price", f"${avg_entry:,.2f}")
                    p_col3.metric("Current Value", f"${current_val:,.2f}")
                    p_col4.metric(f"{pl_color} Live P&L ($ / %)", f"${unrealized_pl:,.2f} ({unrealized_plpc:+.2f}%)")
                    
                    st.write("")
                    if st.button(f"🔴 Exit / Close {pos.symbol} Position Immediately", type="primary", use_container_width=True):
                        try:
                            client.close_position("BTCUSD")
                            st.success("✅ Position closed successfully!")
                            
                            # Send Mobile Notification
                            send_mobile_push(pushbullet_token, "🔴 POSITION CLOSED", f"BTCUSD position closed.\nP&L: ${unrealized_pl:,.2f}")
                            st.rerun()
                        except Exception as close_err:
                            st.error(f"❌ Exit Error: {close_err}")
    except Exception as e:
        st.warning(f"⚠️ Positions fetch karne mein issue: {e}")
else:
    st.warning("🔑 Live Open Positions dekhne ke liye API Keys enter karein.")

st.write("---")

# --- TRADE HISTORY ANALYTICS ---
st.markdown("### 📜 Executed Trade History & Closed Orders")

if api_key and secret_key:
    try:
        client = TradingClient(api_key, secret_key, paper=True)
        orders_request = GetOrdersRequest(
            status=QueryOrderStatus.CLOSED,
            limit=20,
            nested=True
        )
        closed_orders = client.get_orders(filter=orders_request)
        
        if not closed_orders:
            st.info("ℹ️ Abhi tak koi closed trade history available nahi hai.")
        else:
            history_list = []
            for o in closed_orders:
                if o.symbol == "BTCUSD":
                    filled_qty = float(o.qty) if o.qty else 0.0
                    avg_fill_price = float(o.filled_avg_price) if o.filled_avg_price else 0.0
                    order_side = "BUY 🛒" if o.side == OrderSide.BUY else "SELL 🔴"
                    time_created = o.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    
                    history_list.append({
                        "Time": time_created,
                        "Side": order_side,
                        "Type": o.type,
                        "Status": o.status.value.upper(),
                        "Qty (BTC)": f"{filled_qty:.5f}",
                        "Avg Price": f"${avg_fill_price:,.2f}",
                        "Total Value": f"${(filled_qty * avg_fill_price):,.2f}"
                    })
            
            if history_list:
                df_history = pd.DataFrame(history_list)
                st.dataframe(df_history, use_container_width=True)
            else:
                st.info("ℹ️ BTCUSD ke closed orders abhi nahi mile.")
    except Exception as e:
        st.error(f"❌ History Fetch Error: {e}")

# --- CUSTOM MOTIVATIONAL FOOTER TEXT ---
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #c77dff; font-size: 16px; font-weight: bold; padding: 20px; background-color: #161622; border: 1px solid #2d2d44; border-radius: 12px; box-shadow: 0 4px 20px rgba(138, 43, 226, 0.15);'>
    <p>"I only win if you follow the rules. Don't let emotions break my system." 🤖🛡️📈</p>
</div>
""", unsafe_allow_html=True)