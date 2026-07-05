import streamlit as st
import requests
import re
from datetime import datetime

st.set_page_config(layout="wide", page_title="Mayur AI Trading View", page_icon="📈")

# ========== CONFIG ==========
X_HANDLE = "mayur22sharma"

# ========== FUNCTIONS ==========

@st.cache_data(ttl=180) # refresh every 3 mins
def get_x_posts():
    """100% AUTO - X API only"""
    bearer = st.secrets.get("X_BEARER", "")
    if not bearer:
        return None # No token

    try:
        headers = {"Authorization": f"Bearer {bearer}"}

        # Get user ID
        user_res = requests.get(
            f"https://api.twitter.com/2/users/by/username/{X_HANDLE}",
            headers=headers, timeout=10
        ).json()
        user_id = user_res['data']['id']

        # Get last 10 tweets
        tweets_res = requests.get(
            f"https://api.twitter.com/2/users/{user_id}/tweets?max_results=10&tweet.fields=created_at,public_metrics",
            headers=headers, timeout=10
        ).json()

        posts = []
        for t in tweets_res.get('data', []):
            text = t['text']
            tickers = re.findall(r'\$([A-Z]{1,6})', text)
            posts.append({
                "text": text,
                "date": t['created_at'][:16].replace('T', ' '),
                "tickers": tickers,
                "likes": t['public_metrics']['like_count']
            })
        return posts
    except Exception as e:
        return []

@st.cache_data(ttl=300)
def get_price(ticker):
    """Yahoo Finance"""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=6mo"
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=5).json()
        closes = r['chart']['result'][0]['indicators']['quote'][0]['close']
        return [c for c in closes if c is not None]
    except:
        return []

def get_signal(prices):
    """BUY / HOLD / SELL"""
    if len(prices) < 50:
        return "HOLD", "Loading data...", 50

    sma20 = sum(prices[-20:]) / 20
    sma50 = sum(prices[-50:]) / 50
    price = prices[-1]

    # RSI 14
    gains, losses = [], []
    for i in range(1, 15):
        change = prices[-i] - prices[-i-1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))

    avg_gain = sum(gains) / 14 or 0.01
    avg_loss = sum(losses) / 14 or 0.01
    rsi = 100 - (100 / (1 + avg_gain/avg_loss))

    uptrend = price > sma20 > sma50
    downtrend = price < sma20 < sma50
    confidence = min(95, max(55, int(abs(rsi-50)*1.5 + abs(price-sma50)/sma50*100)))

    if uptrend and 45 < rsi < 68:
        return "BUY", f"Uptrend confirmed. SMA20 {sma20:.1f} > SMA50 {sma50:.1f}. RSI {rsi:.0f}", confidence
    elif downtrend and rsi < 45:
        return "SELL", f"Downtrend. Below SMAs. RSI {rsi:.0f} weak", confidence
    elif rsi > 75:
        return "SELL", f"Overbought extreme. RSI {rsi:.0f}", confidence
    elif rsi < 30:
        return "BUY", f"Oversold bounce. RSI {rsi:.0f}", confidence
    else:
        return "HOLD", f"Consolidation. SMA20:{sma20:.1f} SMA50:{sma50:.1f} RSI:{rsi:.0f}", confidence

def generate_mayur_take(ticker, x_post, prices):
    signal, reason, conf = get_signal(prices)
    price = prices[-1]
    change = (price/prices[-2]-1)*100

    color = "🟢" if signal == "BUY" else "🔴" if signal == "SELL" else "🟡"
    emoji = "🚀" if signal=="BUY" else "⚠️" if signal=="SELL" else "⏸️"

    return f"""{color} **{signal} ${ticker} | {conf}% confidence** {emoji}

**Price**: ${price:.2f} ({change:+.2f}%)
**X Signal**: "{x_post[:100]}..."

**Analysis**: {reason}
**Prediction**: {"Target +3-5% next week" if signal=="BUY" else "Risk -3-5% downside" if signal=="SELL" else "Range-bound"}

*Auto-generated from @mayur22sharma + market data*
"""

# ========== UI ==========
st.title("Mayur AI Trading View")
st.caption(f"Auto-sync @mayur22sharma | {datetime.now().strftime('%d %b %Y %H:%M SGT')}")

ticker = st.sidebar.text_input("Ticker", "NVDA").upper()

# Check X API
x_posts = get_x_posts()

if x_posts is None:
    st.error("🔑 X API not connected")
    st.info("""
    **One-time setup for 100% auto:**
    1. Go to developer.x.com → Sign up free
    2. Create Project → copy **Bearer Token**
    3. Streamlit Cloud → Settings → Secrets → add:
