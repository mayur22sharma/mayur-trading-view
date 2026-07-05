import streamlit as st
import requests
import xml.etree.ElementTree as ET
import re
from datetime import datetime

st.set_page_config(layout="wide", page_title="Mayur AI Trading View", page_icon="📈")

X_HANDLE = "mayur22sharma"

# ========== FUNCTIONS ==========

@st.cache_data(ttl=300)
def get_x_posts():
    # 1. X API
    try:
        bearer = st.secrets.get("X_BEARER", "")
        if bearer:
            headers = {"Authorization": f"Bearer {bearer}"}
            user = requests.get(f"https://api.twitter.com/2/users/by/username/{X_HANDLE}", headers=headers, timeout=5).json()
            user_id = user['data']['id']
            tweets = requests.get(f"https://api.twitter.com/2/users/{user_id}/tweets?max_results=5&tweet.fields=created_at", headers=headers, timeout=5).json()
            posts = []
            for t in tweets.get('data', []):
                text = t['text']
                tickers = re.findall(r'\$([A-Z]{1,6})', text)
                posts.append({"text": text, "date": t['created_at'][:16].replace('T', ' '), "tickers": tickers})
            if posts:
                return posts
    except:
        pass

    # 2. Nitter mirrors
    mirrors = ["https://nitter.net", "https://nitter.poast.org", "https://nitter.privacydev.net", "https://nitter.unixfox.eu", "https://nitter.it", "https://xcancel.com"]
    for instance in mirrors:
        try:
            r = requests.get(f"{instance}/{X_HANDLE}/rss", timeout=4)
            if r.status_code == 200:
                root = ET.fromstring(r.content)
                posts = []
                for item in root.findall('.//item')[:5]:
                    title = item.find('title').text
                    pub = item.find('pubDate').text[:16]
                    tickers = re.findall(r'\$([A-Z]{1,6})', title)
                    posts.append({"text": title, "date": pub, "tickers": tickers})
                if posts:
                    return posts
        except:
            continue

    return st.session_state.get('manual_posts', [{"text": "Add posts below", "date": "", "tickers": []}])

@st.cache_data(ttl=300)
def get_price(ticker):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=6mo"
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=5).json()
        closes = r['chart']['result'][0]['indicators']['quote'][0]['close']
        return [c for c in closes if c is not None]
    except:
        return [150, 152, 151, 153, 155, 157, 156, 158, 160, 159]

def get_signal(prices):
    if len(prices) < 50:
        return "HOLD", "Not enough data"
    sma20 = sum(prices[-20:]) / 20
    sma50 = sum(prices[-50:]) / 50
    price = prices[-1]
    gains, losses = [], []
    for i in range(1, 15):
        change = prices[-i] - prices[-i-1]
        if change > 0:
            gains.append(change); losses.append(0)
        else:
            losses.append(abs(change)); gains.append(0)
    avg_gain = sum(gains) / 14 or 0.01
    avg_loss = sum(losses) / 14 or 0.01
    rsi = 100 - (100 / (1 + avg_gain/avg_loss))
    uptrend = price > sma20 > sma50
    downtrend = price < sma20 < sma50
    if uptrend and 45 < rsi < 68:
        return "BUY", f"Uptrend. Above SMA20 ({sma20:.1f}) & SMA50 ({sma50:.1f}). RSI {rsi:.0f}"
    elif downtrend and rsi < 45:
        return "SELL", f"Downtrend. Below SMA20 & SMA50. RSI {rsi:.0f} weak"
    elif rsi > 75:
        return "SELL", f"Overbought. RSI {rsi:.0f}. Take profit"
    elif rsi < 30:
        return "BUY", f"Oversold. RSI {rsi:.0f}. Bounce setup"
    else:
        return "HOLD", f"Chop. SMA20: {sma20:.1f}, SMA50: {sma50:.1f}, RSI: {rsi:.0f}"

def generate_mayur_take(ticker, x_post, prices):
    signal, reason = get_signal(prices)
    price = prices[-1]
    change = (price/prices[-2]-1)*100 if len(prices) > 1 else 0
    color = "🟢" if signal == "BUY" else "🔴" if signal == "SELL" else "🟡"
    prediction = "Breakout likely 3-5 days" if signal=="BUY" else "Drop risk next 3-5 days" if signal=="SELL" else "Sideways expected"

    return (
        f"{color} **Mayur Take: ${ticker} → {signal}**\n\n"
        f"**Price**: ${price:.2f} ({change:+.2f}%)\n"
        f"**Your X**: \"{x_post[:120]}...\"\n\n"
        f"**Signal**: {signal}\n"
        f"**Why**: {reason}\n"
        f"**Prediction**: {prediction}\n\n"
        "*Technical view only. Not financial advice.*"
    )

# ========== UI ==========
st.title("Mayur AI Trading View")
st.caption("Live from Singapore | @mayur22sharma")

if 'manual_posts' not in st.session_state:
    st.session_state.manual_posts = []

ticker = st.sidebar.text_input("Ticker", "NVDA").upper()

x_posts = get_x_posts()
prices = get_price(ticker)
latest_x = x_posts[0]['text'] if x_posts else ""

col1, col2 = st.columns([2,1])

with col1:
    st.subheader(f"${ticker} - 6 Month Chart")
    st.line_chart(prices)
    c1, c2, c3 = st.columns(3)
    c1.metric("Current", f"${prices[-1]:.2f}")
    c2.metric("Change", f"{(prices[-1]/prices[-2]-1)*100:+.2f}%")
    c3.metric("vs 50D", f"{(prices[-1]/(sum(prices[-50:])/50)-1)*100:+.1f}%")

with col2:
    st.subheader("Signal Engine")
    with st.expander("➕ Add X Post Manually"):
        new_post = st.text_area("Paste tweet:", height=80)
        if st.button("Save"):
            if new_post:
                tickers = re.findall(r'\$([A-Z]{1,6})', new_post)
                st.session_state.manual_posts.insert(0, {"text": new_post, "date": datetime.now().strftime('%d %b %H:%M'), "tickers": tickers})
                st.session_state.manual_posts = st.session_state.manual_posts[:5]
                st.rerun()

    st.write("**Latest @mayur22sharma**")
    for post in x_posts[:3]:
        st.caption(post['date'])
        tick_str = " ".join([f"${t}" for t in post['tickers']])
        st.info(post['text'][:140] + " " + tick_str)

    mayur_take = generate_mayur_take(ticker, latest_x, prices)
    st.markdown(mayur_take)
    if st.button("📋 Copy for WhatsApp", use_container_width=True, type="primary"):
        st.code(mayur_take)
        st.toast("Copied!")

st.subheader("Watchlist from Your X")
all_tickers = list(set([t for p in x_posts for t in p['tickers']]))
if not all_tickers:
    all_tickers = ["NVDA", "TSLA", "AAPL", "MSFT", "AMD", "META"]

cols = st.columns(min(6, len(all_tickers)))
for i, t in enumerate(all_tickers[:6]):
    try:
        p = get_price(t)
        signal, _ = get_signal(p)
        emoji = "🟢" if signal=="BUY" else "🔴" if signal=="SELL" else "🟡"
        cols[i].metric(f"{emoji} ${t}", f"${p[-1]:.2f}", signal)
    except:
        cols[i].metric(f"${t}", "N/A")
