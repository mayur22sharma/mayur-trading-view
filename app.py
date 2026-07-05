import streamlit as st
import requests
import xml.etree.ElementTree as ET
import re
from datetime import datetime

st.set_page_config(layout="wide", page_title="Mayur AI Trading View", page_icon="📈")

X_HANDLE = "mayur22sharma"

# ========== DATA FUNCTIONS ==========

@st.cache_data(ttl=180)
def get_x_posts():
    """Auto pull from X API, fallback to Nitter"""
    # 1. X API
    try:
        bearer = st.secrets.get("X_BEARER", "")
        if bearer:
            headers = {"Authorization": f"Bearer {bearer}"}
            user = requests.get(f"https://api.twitter.com/2/users/by/username/{X_HANDLE}", headers=headers, timeout=5).json()
            user_id = user['data']['id']
            tweets = requests.get(f"https://api.twitter.com/2/users/{user_id}/tweets?max_results=10&tweet.fields=created_at", headers=headers, timeout=5).json()
            posts = []
            for t in tweets.get('data', []):
                text = t['text']
                tickers = re.findall(r'\$([A-Z]{1,6})', text)
                posts.append({"text": text, "date": t['created_at'][:16].replace('T', ' '), "tickers": tickers})
            if posts:
                return posts
    except:
        pass

    # 2. Nitter fallback
    mirrors = ["https://nitter.net", "https://nitter.poast.org", "https://nitter.privacydev.net", "https://xcancel.com"]
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
    return []

@st.cache_data(ttl=300)
def get_ohlc(ticker):
    """Get OHLC for candles and PE"""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=3mo"
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=5).json()
        q = r['chart']['result'][0]['indicators']['quote'][0]
        return {
            'open': [x for x in q['open'] if x],
            'high': [x for x in q['high'] if x],
            'low': [x for x in q['low'] if x],
            'close': [x for x in q['close'] if x]
        }
    except:
        return {'open':[150]*60, 'high':[152]*60, 'low':[148]*60, 'close':[150]*60}

@st.cache_data(ttl=3600)
def get_pe_ratio(ticker):
    try:
        url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}?modules=defaultKeyStatistics"
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=5).json()
        stats = r['quoteSummary']['result'][0]['defaultKeyStatistics']
        pe = stats.get('trailingPE', {}).get('raw')
        return round(pe,1) if pe else None
    except:
        return None

# ========== ANALYSIS FUNCTIONS ==========

def detect_candle_pattern(ohlc):
    if len(ohlc['close']) < 2:
        return "None", "NEUTRAL"
    o1, h1, l1, c1 = ohlc['open'][-2], ohlc['high'][-2], ohlc['low'][-2], ohlc['close'][-2]
    o2, h2, l2, c2 = ohlc['open'][-1], ohlc['high'][-1], ohlc['low'][-1], ohlc['close'][-1]
    body1 = abs(c1 - o1)
    body2 = abs(c2 - o2)

    if c1 < o1 and c2 > o2 and o2 < c1 and c2 > o1 and body2 > body1:
        return "Bullish Engulfing", "BUY"
    if c1 > o1 and c2 < o2 and o2 > c1 and c2 < o1 and body2 > body1:
        return "Bearish Engulfing", "SELL"

    lower_wick = min(o2, c2) - l2
    upper_wick = h2 - max(o2, c2)
    if lower_wick > body2 * 2 and upper_wick < body2 * 0.5:
        return "Hammer", "BUY"
    if upper_wick > body2 * 2 and lower_wick < body2 * 0.5:
        return "Shooting Star", "SELL"

    if body2 < (h2-l2) * 0.1:
        return "Doji", "NEUTRAL"

    return "No pattern", "NEUTRAL"

def get_signal(ohlc, pe):
    closes = ohlc['close']
    if len(closes) < 50:
        return "HOLD", "Loading", 50

    sma20 = sum(closes[-20:]) / 20
    sma50 = sum(closes[-50:]) / 50
    price = closes[-1]

    gains, losses = [], []
    for i in range(1, 15):
        ch = closes[-i] - closes[-i-1]
        gains.append(max(ch,0))
        losses.append(max(-ch,0))
    rsi = 100 - (100 / (1 + (sum(gains)/14)/(sum(losses)/14 or 0.01)))

    pattern, candle_sig = detect_candle_pattern(ohlc)
    uptrend = price > sma20 > sma50
    downtrend = price < sma20 < sma50

    pe_text = f"PE {pe}" if pe else "PE N/A"
    confidence = int(60 + abs(rsi-50)*0.6)

    if uptrend and candle_sig == "BUY" and (not pe or pe < 30):
        return "BUY", f"{pattern} + uptrend + {pe_text}", confidence
    if downtrend and candle_sig == "SELL":
        return "SELL", f"{pattern} + downtrend + {pe_text}", confidence
    if rsi > 75 and pe and pe > 30:
        return "SELL", f"Overbought RSI {rsi:.0f} + {pe_text}", confidence
    if rsi < 30 and pe and pe < 20:
        return "BUY", f"Oversold + {pe_text}", confidence
    if candle_sig == "BUY":
        return "BUY", f"Candle: {pattern}", confidence-10
    if candle_sig == "SELL":
        return "SELL", f"Candle: {pattern}", confidence-10

    return "HOLD", f"{pe_text} | RSI {rsi:.0f}", confidence

def generate_take(ticker, x_post, ohlc, pe, signal, reason, conf):
    price = ohlc['close'][-1]
    chg = (price/ohlc['close'][-2]-1)*100
    color = "🟢" if signal=="BUY" else "🔴" if signal=="SELL" else "🟡"
    return (
        f"{color} **{signal} ${ticker} | {conf}%**\n\n"
        f"Price: ${price:.2f} ({chg:+.2f}%) | PE: {pe if pe else 'N/A'}\n"
        f"X: \"{x_post[:100]}...\"\n\n"
        f"Why: {reason}\n\n"
        f"*Auto: Candle + PE + Technical*"
    )

# ========== UI ==========

st.title("Mayur AI Trading View")
st.caption(f"Auto @mayur22sharma | {datetime.now().strftime('%d %b %H:%M SGT')}")

ticker = st.sidebar.text_input("Ticker", "NVDA").upper()

x_posts = get_x_posts()
if not x_posts:
    st.warning("Add X_BEARER in Streamlit Secrets for auto feed")
    x_posts = [{"text": "Demo mode", "date": "", "tickers": ["NVDA","TSLA"]}]

ohlc = get_ohlc(ticker)
pe = get_pe_ratio(ticker)
signal, reason, conf = get_signal(ohlc, pe)
pattern, _ = detect_candle_pattern(ohlc)

col1, col2 = st.columns([2,1])

with col1:
    st.subheader(f"${ticker} Chart")
    st.line_chart(ohlc['close'])
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Price", f"${ohlc['close'][-1]:.2f}")
    c2.metric("Signal", signal)
    c3.metric("PE", pe if pe else "N/A")
    c4.metric("Candle", pattern)

with col2:
    st.subheader("Live X")
    for p in x_posts[:3]:
        st.caption(p['date'])
        st.info(p['text'][:150])

    st.divider()
    take = generate_take(ticker, x_posts[0]['text'], ohlc, pe, signal, reason, conf)
    st.markdown(take)
    if st.button("📋 Copy", use_container_width=True):
        st.code(take)

st.subheader("Watchlist from X")
tickers = list(dict.fromkeys([t for p in x_posts for t in p['tickers']]))[:6]
if tickers:
    cols = st.columns(len(tickers))
    for i,t in enumerate(tickers):
        o = get_ohlc(t)
        p = get_pe_ratio(t)
        s,_,c = get_signal(o,p)
        emoji = "🟢" if s=="BUY" else "🔴" if s=="SELL" else "🟡"
        cols[i].metric(f"{emoji} ${t}", f"${o['close'][-1]:.1f}", f"{s} {c}%")
