import streamlit as st
import requests
import xml.etree.ElementTree as ET
import re
from datetime import datetime

st.set_page_config(layout="wide", page_title="Mayur AI Trading View", page_icon="📈")
X_HANDLE = "mayur22sharma"

# ========== DATA ==========

@st.cache_data(ttl=180)
def get_x_posts():
    try:
        bearer = st.secrets.get("X_BEARER", "")
        if bearer:
            headers = {"Authorization": f"Bearer {bearer}"}
            user = requests.get(f"https://api.twitter.com/2/users/by/username/{X_HANDLE}", headers=headers, timeout=5).json()
            uid = user['data']['id']
            tweets = requests.get(f"https://api.twitter.com/2/users/{uid}/tweets?max_results=10&tweet.fields=created_at", headers=headers, timeout=5).json()
            posts = []
            for t in tweets.get('data', []):
                posts.append({"text": t['text'], "date": t['created_at'][:16].replace('T',' '), "tickers": re.findall(r'\$([A-Z]{1,6})', t['text'])})
            if posts: return posts
    except: pass
    mirrors = ["https://nitter.net","https://nitter.poast.org","https://xcancel.com"]
    for inst in mirrors:
        try:
            r = requests.get(f"{inst}/{X_HANDLE}/rss", timeout=4)
            if r.status_code == 200:
                root = ET.fromstring(r.content)
                posts = []
                for item in root.findall('.//item')[:5]:
                    title = item.find('title').text or ""
                    posts.append({"text": title, "date": "", "tickers": re.findall(r'\$([A-Z]{1,6})', title)})
                if posts: return posts
        except: continue
    return []

@st.cache_data(ttl=300)
def get_ohlc(ticker):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=3mo"
        r = requests.get(url, headers={'User-Agent':'Mozilla/5.0'}, timeout=5).json()
        q = r['chart']['result'][0]['indicators']['quote'][0]
        data = []
        for i in range(len(q['close'])):
            if q['open'][i] and q['high'][i] and q['low'][i] and q['close'][i]:
                data.append({'o':q['open'][i],'h':q['high'][i],'l':q['low'][i],'c':q['close'][i]})
        return {'open':[d['o'] for d in data],'high':[d['h'] for d in data],'low':[d['l'] for d in data],'close':[d['c'] for d in data]}
    except:
        return {'open':[150]*60,'high':[152]*60,'low':[148]*60,'close':[150]*60}

@st.cache_data(ttl=3600)
def get_pe_ratio(ticker):
    try:
        url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}?modules=defaultKeyStatistics"
        r = requests.get(url, headers={'User-Agent':'Mozilla/5.0'}, timeout=5).json()
        pe = r['quoteSummary']['result'][0]['defaultKeyStatistics'].get('trailingPE',{}).get('raw')
        return round(pe,1) if pe else None
    except: return None

# ========== NEW: CEO & RESEARCH ENGINE ==========

@st.cache_data(ttl=3600)
def get_ceo_name(ticker):
    try:
        url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}?modules=assetProfile"
        r = requests.get(url, headers={'User-Agent':'Mozilla/5.0'}, timeout=5).json()
        officers = r['quoteSummary']['result'][0]['assetProfile'].get('companyOfficers',[])
        if officers: return officers[0]['name']
    except: pass
    ceo_map = {"NVDA":"Jensen Huang","TSLA":"Elon Musk","AAPL":"Tim Cook","MSFT":"Satya Nadella","META":"Mark Zuckerberg","AMD":"Lisa Su"}
    return ceo_map.get(ticker, "CEO")

def score_sentiment(text):
    pos_words = ["bullish","growth","beat","record","strong","up","buy","optimistic","surge","profit","win","breakout","cooking","accumulate","long"]
    neg_words = ["bearish","miss","down","cut","sell","weak","loss","drop","risk","lawsuit","crash","bubble","overvalued","short"]
    text = text.lower()
    pos = sum(1 for w in pos_words if w in text)
    neg = sum(1 for w in neg_words if w in text)
    if pos==0 and neg==0: return 0
    return (pos - neg) / (pos + neg)

@st.cache_data(ttl=1800)
def get_ceo_sentiment(ticker):
    ceo = get_ceo_name(ticker)
    try:
        query = f"{ticker} {ceo} CEO"
        url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
        r = requests.get(url, timeout=5)
        root = ET.fromstring(r.content)
        headlines = [item.find('title').text for item in root.findall('.//item')[:5]]
        if not headlines: return ceo, "No news", 0
        scores = [score_sentiment(h) for h in headlines]
        avg = sum(scores)/len(scores)
        label = "Bullish" if avg > 0.2 else "Bearish" if avg < -0.2 else "Neutral"
        return ceo, f"{label} ({'; '.join(headlines[:2])})", avg
    except:
        return ceo, "No news", 0

def get_mayur_research_score(x_posts, ticker):
    relevant = [p['text'] for p in x_posts if ticker in p['tickers'] or ticker in p['text']]
    if not relevant:
        relevant = [p['text'] for p in x_posts[:3]]
    if not relevant: return "No research", 0
    scores = [score_sentiment(t) for t in relevant]
    avg = sum(scores)/len(scores)
    label = "High Conviction Bullish" if avg > 0.3 else "Cautious/Bearish" if avg < -0.2 else "Neutral"
    return f"{label} - \"{relevant[0][:80]}...\"", avg

# ========== ANALYSIS ==========

def detect_candle(ohlc):
    if len(ohlc['close']) < 2: return "None","NEUTRAL"
    o1,c1 = ohlc['open'][-2], ohlc['close'][-2]
    o2,h2,l2,c2 = ohlc['open'][-1], ohlc['high'][-1], ohlc['low'][-1], ohlc['close'][-1]
    b1,b2 = abs(c1-o1), abs(c2-o2) or 0.01
    if c1<o1 and c2>o2 and o2<c1 and c2>o1 and b2>b1: return "Bullish Engulfing","BUY"
    if c1>o1 and c2<o2 and o2>c1 and c2<o1 and b2>b1: return "Bearish Engulfing","SELL"
    if (min(o2,c2)-l2) > b2*2: return "Hammer","BUY"
    if (h2-max(o2,c2)) > b2*2: return "Shooting Star","SELL"
    return "No pattern","NEUTRAL"

def get_final_signal(ohlc, pe, ceo_score, mayur_score):
    closes = ohlc['close']
    sma20 = sum(closes[-20:])/20
    sma50 = sum(closes[-50:])/50
    price = closes[-1]
    rsi_gains = []
    rsi_losses = []
    for i in range(1,15):
        ch = closes[-i]-closes[-i-1]
        rsi_gains.append(max(ch,0))
        rsi_losses.append(max(-ch,0))
    rsi = 100 - (100/(1+((sum(rsi_gains)/14)/((sum(rsi_losses)/14) or 0.01))))

    pattern, candle_sig = detect_candle(ohlc)
    uptrend = price > sma20 > sma50
    downtrend = price < sma20 < sma50

    # Weighted scoring - your secret sauce
    tech_score = 1 if uptrend and 40<rsi<70 else -1 if downtrend else 0
    pe_score = 1 if pe and pe<20 else -1 if pe and pe>35 else 0
    # ceo_score and mayur_score are -1 to 1

    final = (tech_score*0.5) + (pe_score*0.2) + (ceo_score*0.15) + (mayur_score*0.15)

    if final >= 0.4: sig="BUY"
    elif final <= -0.4: sig="SELL"
    else: sig="HOLD"

    conf = min(95, max(60, int(70 + abs(final)*30 + abs(rsi-50)*0.3)))
    reason = f"Tech:{tech_score} PE:{pe_score} CEO:{ceo_score:.1f} Mayur:{mayur_score:.1f} | {pattern} RSI {rsi:.0f}"
    return sig, reason, conf, pattern, rsi

# ========== UI ==========

st.title("Mayur AI Trading View - Research Edition")
st.caption(f"Powered by Mayur Research + CEO Intel | {datetime.now().strftime('%d %b %H:%M SGT')}")

ticker = st.sidebar.text_input("Ticker","NVDA").upper()
x_posts = get_x_posts()
if not x_posts:
    x_posts = [{"text":"Demo $NVDA cooking bullish breakout","date":"","tickers":["NVDA"]}]

ohlc = get_ohlc(ticker)
pe = get_pe_ratio(ticker)
ceo_name, ceo_news, ceo_score = get_ceo_sentiment(ticker)
mayur_text, mayur_score = get_mayur_research_score(x_posts, ticker)
signal, reason, conf, pattern, rsi = get_final_signal(ohlc, pe, ceo_score, mayur_score)

col1, col2 = st.columns([2,1])
with col1:
    st.subheader(f"${ticker} | ${ohlc['close'][-1]:.2f} | {signal} {conf}%")
    st.line_chart(ohlc['close'])
    m1,m2,m3,m4 = st.columns(4)
    m1.metric("Signal",signal)
    m2.metric("PE", pe if pe else "N/A")
    m3.metric("Candle",pattern)
    m4.metric("RSI",f"{rsi:.0f}")

    st.divider()
    st.subheader("🧠 Research Intel")
    st.info(f"**CEO {ceo_name} Take:** {ceo_news} (Score {ceo_score:+.1f})")
    st.success(f"**Your Research (Mayur):** {mayur_text} (Score {mayur_score:+.1f})")
    st.caption(f"**Combined Logic:** {reason}")

with col2:
    st.subheader("Live X Feed")
    for p in x_posts[:3]:
        st.info(p['text'][:160])

    take = f"🟢 **{signal} ${ticker} | {conf}%**\nPrice ${ohlc['close'][-1]:.2f} PE {pe}\nCEO {ceo_name}: {ceo_news[:60]}\nMayur: {mayur_text[:60]}\nReason: {reason}"
    st.markdown(take)
    if st.button("📋 Copy for WhatsApp", use_container_width=True):
        st.code(take)

st.subheader("Watchlist - CEO + Mayur Score")
ticks = list(dict.fromkeys([t for p in x_posts for t in p['tickers']]))[:5] or ["NVDA","TSLA","AAPL"]
cols = st.columns(len(ticks))
for i,t in enumerate(ticks):
    o = get_ohlc(t)
    pe_t = get_pe_ratio(t)
    _,_,ceo_s = get_ceo_sentiment(t)
    _,may_s = get_mayur_research_score(x_posts, t)
    s,_,c,_,_ = get_final_signal(o, pe_t, ceo_s, may_s)
    emoji = "🟢" if s=="BUY" else "🔴" if s=="SELL" else "🟡"
    cols[i].metric(f"{emoji} ${t}", f"${o['close'][-1]:.0f}", f"{s} {c}%")
