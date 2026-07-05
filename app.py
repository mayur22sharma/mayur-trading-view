import streamlit as st
import pandas as pd
import yfinance as yf
import feedparser
import requests
from datetime import datetime
import re
import ta

st.set_page_config(layout="wide", page_title="Mayur AI Trading View", page_icon="📈")

# ========== CONFIG ==========
X_HANDLE = "mayur22sharma"
TWILIO_SID = st.secrets.get("TWILIO_SID", "")
TWILIO_TOKEN = st.secrets.get("TWILIO_TOKEN", "")
TWILIO_WHATSAPP_FROM = st.secrets.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
WHATSAPP_TO = st.secrets.get("WHATSAPP_TO", "")

# ========== SIDEBAR ==========
st.sidebar.title("Mayur Take Control")
ticker = st.sidebar.text_input("Ticker", "NVDA").upper()
st.sidebar.caption("Hosted free on Streamlit Cloud")

# ========== FUNCTIONS ==========

@st.cache_data(ttl=300)
def get_mayur_x_posts(limit=5):
    try:
        rss_url = f"https://nitter.net/{X_HANDLE}/rss"
        feed = feedparser.parse(rss_url)
        posts = []
        for entry in feed.entries[:limit]:
            tickers = re.findall(r'\$([A-Z]{1,6})', entry.title)
            posts.append({
                "text": entry.title,
                "date": entry.published[:16],
                "tickers": tickers,
            })
        return posts
    except:
        return [{"text": "Could not fetch @mayur22sharma.", "date": "", "tickers": []}]

@st.cache_data(ttl=300)
def get_stock_data(ticker):
    """Replaces OpenBB with yfinance - works on Streamlit Cloud"""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="6mo")
        info = stock.info
        df['RSI'] = ta.momentum.RSIIndicator(df['Close']).rsi()
        return df, info
    except:
        return pd.DataFrame(), {}

def generate_mayur_take(ticker, x_post, df, info):
    try:
        price = df['Close'].iloc[-1]
        rsi = df['RSI'].iloc[-1]
        vol_ratio = df['Volume'].iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1]
        zone = "Overbought" if rsi > 70 else "Oversold" if rsi < 30 else "Neutral"

        story = f"""
**Mayur Take: ${ticker}** | {datetime.now().strftime('%d %b %H:%M SGT')}

**Your X Signal**: "{x_post[:120]}..."

**Market Data**: ${price:.2f} | RSI {rsi:.0f} | Vol {vol_ratio:.1f}x avg | {zone}

**Mayur's Call**: {"Breakout setup forming" if vol_ratio > 1.3 and 40 < rsi < 70 else "Wait for confirmation"} near ${price*1.02:.2f}.

*Personal view for education. Not financial advice. DYOR.*
"""
        return story
    except:
        return "Error generating Mayur Take. Check ticker."

def send_whatsapp(message):
    if not all([TWILIO_SID, TWILIO_TOKEN, WHATSAPP_TO]):
        return "⚠️ Add Twilio secrets in Streamlit Cloud Settings"
    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json"
        data = {"From": TWILIO_WHATSAPP_FROM, "To": WHATSAPP_TO, "Body": message}
        r = requests.post(url, data=data, auth=(TWILIO_SID, TWILIO_TOKEN))
        return "✅ Sent to WhatsApp" if r.status_code == 201 else f"Twilio Error: {r.json().get('message')}"
    except Exception as e:
        return f"Error: {e}"

# ========== MAIN APP ==========
st.title("Mayur AI Trading View")
st.caption("yfinance + @mayur22sharma X Feed + AI Stories → WhatsApp | 100% Free Cloud")

with st.spinner("Loading data..."):
    df, info = get_stock_data(ticker)
    x_posts = get_mayur_x_posts()
    latest_x = x_posts[0]['text'] if x_posts else "No posts found"

if df.empty:
    st.error("Invalid ticker or yfinance rate limit. Try NVDA, TSLA, AAPL")
    st.stop()

col1, col2 = st.columns([2,1])

with col1:
    st.subheader(f"${ticker} Chart")
    st.line_chart(df['Close'])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Last", f"${df['Close'].iloc[-1]:.2f}")
    c2.metric("1M %", f"{(df['Close'].iloc[-1]/df['Close'].iloc[-22]-1)*100:.1f}%")
    c3.metric("RSI", f"{df['RSI'].iloc[-1]:.0f}")
    c4.metric("Volume", f"{df['Volume'].iloc[-1]/1e6:.1f}M")

with col2:
    st.subheader("Mayur Take Engine")
    st.write("**Latest from @mayur22sharma**")
    for post in x_posts[:3]:
        st.caption(post['date'])
        if post['tickers']:
            st.info(f"{post['text']} 🎯 {', '.join(['$'+t for t in post['tickers']])}")
        else:
            st.info(post['text'])

    mayur_take = generate_mayur_take(ticker, latest_x, df, info)
    st.write("**AI Generated Mayur Take**")
    st.success(mayur_take)

    if st.button("📲 Broadcast to WhatsApp", use_container_width=True, type="primary"):
        result = send_whatsapp(mayur_take)
        st.toast(result)

# Auto Watchlist from your X
st.subheader("Auto Watchlist - From Your X Posts")
all_tickers = list(set([t for post in x_posts for t in post['tickers']]))
if not all_tickers: all_tickers = ["NVDA", "TSLA", "AAPL", "AMD", "MSFT", "META"]

cols = st.columns(6)
for i, t in enumerate(all_tickers[:6]):
    try:
        price = yf.Ticker(t).info.get('currentPrice', 0)
        cols[i].metric(f"${t}", f"{price:.2f}")
    except:
        cols[i].metric(f"${t}", "N/A")

st.caption("Disclaimer: Educational only. Not financial advice.")
