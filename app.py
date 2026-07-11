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
                posts.append({"text": t['text'], "tickers": re.findall(r'\$([A-Z]{1,6})', t['text'])})
            if posts: return posts
    except: pass
    for inst in ["https://nitter.net","https://nitter.poast.org","https://xcancel.com"]:
        try:
            r=requests.get(f"{inst}/{X_HANDLE}/rss",timeout=4)
            if r.status_code==200:
                root=ET.fromstring(r.content)
                posts=[{"text":item.find('title').text or "","tickers":re.findall(r'\$([A-Z]{1,6})',item.find('title').text or "")} for item in root.findall('.//item')[:5]]
                if posts: return posts
        except: continue
    return []

@st.cache_data(ttl=300)
def get_ohlc(ticker):
    try:
        url=f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=3mo"
        r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=5).json()
        q=r['chart']['result'][0]['indicators']['quote'][0]
        data=[]
        for i in range(len(q['close'])):
            if q['open'][i] and q['high'][i] and q['low'][i] and q['close'][i]:
                data.append((q['open'][i],q['high'][i],q['low'][i],q['close'][i]))
        return {'open':[d[0] for d in data],'high':[d[1] for d in data],'low':[d[2] for d in data],'close':[d[3] for d in data]}
    except:
        return {'open':[150]*60,'high':[152]*60,'low':[148]*60,'close':[150]*60}

@st.cache_data(ttl=3600)
def get_pe(ticker):
    try:
        url=f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}?modules=defaultKeyStatistics"
        r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=5).json()
        return r['quoteSummary']['result'][0]['defaultKeyStatistics'].get('trailingPE',{}).get('raw')
    except: return None

# ========== RESEARCH ENGINE ==========
def score_sentiment(text):
    pos=["bullish","growth","beat","record","strong","up","buy","surge","profit","breakout","cooking","long","upgrade","positive"]
    neg=["bearish","miss","down","cut","sell","weak","loss","drop","downgrade","negative","lawsuit","crash"]
    t=text.lower(); p=sum(w in t for w in pos); n=sum(w in t for w in neg)
    return (p-n)/(p+n or 1)

@st.cache_data(ttl=3600)
def get_ceo_name(ticker):
    try:
        url=f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}?modules=assetProfile"
        r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=5).json()
        return r['quoteSummary']['result'][0]['assetProfile']['companyOfficers'][0]['name']
    except:
        return {"NVDA":"Jensen Huang","TSLA":"Elon Musk","AAPL":"Tim Cook","MSFT":"Satya Nadella","META":"Mark Zuckerberg","AMD":"Lisa Su"}.get(ticker,"CEO")

@st.cache_data(ttl=1800)
def get_news_sentiment(query, source=""):
    try:
        q=f"{query} {source}".strip()
        url=f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
        r=requests.get(url,timeout=5); root=ET.fromstring(r.content)
        heads=[i.find('title').text for i in root.findall('.//item')[:4]]
        if not heads: return "No news", 0
        sc=sum(score_sentiment(h) for h in heads)/len(heads)
        return heads[0][:110], sc
    except: return "No news", 0

@st.cache_data(ttl=1800)
def get_analyst_sentiment(ticker):
    try:
        url=f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}?modules=recommendationTrend"
        r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=5).json()
        tr=r['quoteSummary']['result'][0]['recommendationTrend']['trend'][0]
        buys=tr.get('strongBuy',0)+tr.get('buy',0); total=sum([tr.get(k,0) for k in ['strongBuy','buy','hold','sell','strongSell']]) or 1
        pct=buys/total
        label=f"{int(pct*100)}% Buy ({buys}/{total} analysts)"
        return label, (pct-0.5)*2
    except: return "No analyst data", 0

# ========== TECHNICAL + LEVELS ==========
def detect_candle(ohlc):
    o1,c1=ohlc['open'][-2],ohlc['close'][-2]; o2,h2,l2,c2=ohlc['open'][-1],ohlc['high'][-1],ohlc['low'][-1],ohlc['close'][-1]
    b1,b2=abs(c1-o1),abs(c2-o2) or 0.01
    if c1<o1 and c2>o2 and o2<c1 and c2>o1 and b2>b1: return "Bullish Engulfing","BUY"
    if c1>o1 and c2<o2 and o2>c1 and c2<o1 and b2>b1: return "Bearish Engulfing","SELL"
    if (min(o2,c2)-l2)>b2*2: return "Hammer","BUY"
    if (h2-max(o2,c2))>b2*2: return "Shooting Star","SELL"
    return "No pattern","NEUTRAL"

def calculate_levels(ohlc, signal):
    closes,highs,lows=ohlc['close'],ohlc['high'],ohlc['low']
    price=closes[-1]; support=min(lows[-20:]); resistance=max(highs[-20:])
    atr=sum(h-l for h,l in zip(highs[-14:],lows[-14:]))/14
    if signal=="BUY":
        buy_low=round(max(support, price*0.97),2); buy_high=round(min(price*1.005, price+atr*0.4),2)
        sell_low=round(price*1.06,2); sell_high=round(min(resistance*1.01, price*1.12),2); stop=round(buy_low*0.93,2)
    elif signal=="SELL":
        buy_low=round(support*0.98,2); buy_high=round(support*1.02,2)
        sell_low=round(price*0.99,2); sell_high=round(price*1.005,2); stop=round(price*1.07,2)
    else:
        buy_low=round(support,2); buy_high=round(sum(closes[-20:])/20,2)
        sell_low=round(sum(closes[-50:])/50,2); sell_high=round(resistance,2); stop=round(support*0.95,2)
    return buy_low,buy_high,sell_low,sell_high,stop

def get_final_signal(ohlc, pe, ceo_sc, cnbc_sc, expert_sc, x_sc):
    closes=ohlc['close']; sma20=sum(closes[-20:])/20; sma50=sum(closes[-50:])/50; price=closes[-1]
    g,l=[],[]
    for i in range(1,15):
        ch=closes[-i]-closes[-i-1]; g.append(max(ch,0)); l.append(max(-ch,0))
    rsi=100-(100/(1+((sum(g)/14)/((sum(l)/14) or 0.01))))
    pat,candle=detect_candle(ohlc)
    tech=1 if price>sma20>sma50 and 40<rsi<70 else -1 if price<sma20<sma50 else 0
    pe_sc=1 if pe and pe<20 else -1 if pe and pe>35 else 0
    final=(tech*0.35)+(pe_sc*0.15)+(ceo_sc*0.15)+(cnbc_sc*0.15)+(expert_sc*0.1)+(x_sc*0.1)
    sig="BUY" if final>=0.25 else "SELL" if final<=-0.25 else "HOLD"
    conf=min(92,max(62,int(68+abs(final)*35)))
    return sig,conf,pat,rsi,final

def build_mayur_take(ticker, sig, conf, ohlc, pe, ceo_name, ceo_news, cnbc_news, expert_label, x_text, rsi, final_score):
    buy_low,buy_high,sell_low,sell_high,stop=calculate_levels(ohlc, sig)
    price=ohlc['close'][-1]
    upside=round((sell_low/price-1)*100,1) if sig=="BUY" else round((price/buy_low-1)*100,1)

    # Line 1: Action + Levels
    if sig=="BUY":
        line1=f"{'🟢' if sig=='BUY' else '🔴'} **MAYUR TAKE: BUY ${ticker} at ${buy_low}-${buy_high} | SELL ${sell_low}-${sell_high} (+{upside}%) | STOP ${stop} | {conf}%**"
    elif sig=="SELL":
        line1=f"🔴 **MAYUR TAKE: SELL ${ticker} at ${sell_low}-${sell_high} | RE-BUY ${buy_low}-${buy_high} | STOP ${stop} | {conf}%**"
    else:
        line1=f"🟡 **MAYUR TAKE: HOLD ${ticker} at ${price:.2f} | BUY ZONE ${buy_low}-${buy_high} | SELL ZONE ${sell_low}-${sell_high} | {conf}%**"

    # Line 2: Deep Research Summary (2 lines max)
    line2=f"Research: OpenBB {detect_candle(ohlc)[0]} RSI {rsi:.0f} | CNBC: {cnbc_news[:55]} | CEO {ceo_name.split()[-1]}: {ceo_news[:50]} | Experts: {expert_label} | X: {x_text[:40]}"
    return line1, line2, buy_low, buy_high, sell_low, sell_high, stop

# ========== UI ==========
st.title("Mayur AI Trading View")
st.caption(f"Deep Research Edition | OpenBB + CNBC + CEO + Experts + X | {datetime.now().strftime('%d %b %H:%M SGT')}")
ticker=st.sidebar.text_input("Ticker","NVDA").upper()

x_posts=get_x_posts()
ohlc=get_ohlc(ticker)
pe=get_pe(ticker)
ceo_name=get_ceo_name(ticker)
ceo_news,ceo_sc=get_news_sentiment(f"{ticker} {ceo_name}")
cnbc_news,cnbc_sc=get_news_sentiment(ticker, "CNBC")
expert_label,expert_sc=get_analyst_sentiment(ticker)
x_text, x_sc = (x_posts[0]['text'][:100], score_sentiment(x_posts[0]['text'])) if x_posts else ("No X data",0)

sig,conf,pat,rsi,final=get_final_signal(ohlc, pe, ceo_sc, cnbc_sc, expert_sc, x_sc)
line1,line2,bl,bh,sl,sh,stop=build_mayur_take(ticker,sig,conf,ohlc,pe,ceo_name,ceo_news,cnbc_news,expert_label,x_text,rsi,final)

col1,col2=st.columns([2,1])
with col1:
    st.markdown(line1)
    st.caption(line2)
    st.line_chart(ohlc['close'])
    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric("Price",f"${ohlc['close'][-1]:.2f}")
    c2.metric("Signal",sig)
    c3.metric("PE",pe or "N/A")
    c4.metric("Candle",pat)
    c5.metric("RSI",f"{rsi:.0f}")
    st.divider()
    st.markdown(f"**Buy Zone:** ${bl} - ${bh} | **Sell Zone:** ${sl} - ${sh} | **Stop:** ${stop}")
    st.info(f"**CEO {ceo_name}:** {ceo_news}")
    st.success(f"**CNBC:** {cnbc_news}")
    st.warning(f"**Experts:** {expert_label}")

with col2:
    st.subheader("Live X")
    if not x_posts: st.info("Add X_BEARER in Secrets")
    else:
        for p in x_posts[:3]: st.info(p['text'][:160])
    st.code(f"{line1}\n{line2}")

st.subheader("Watchlist - Deep Research")
tickers=list(dict.fromkeys([t for p in x_posts for t in p['tickers']]))[:5] or ["NVDA","TSLA","AAPL","MSFT","AMD"]
cols=st.columns(len(tickers))
for i,t in enumerate(tickers):
    o=get_ohlc(t); pe_t=get_pe(t)
    _,ceo_s=get_news_sentiment(f"{t} {get_ceo_name(t)}"); _,cnbc_s=get_news_sentiment(t,"CNBC"); _,exp_s=get_analyst_sentiment(t)
    s,c,_,_,_=get_final_signal(o,pe_t,ceo_s,cnbc_s,exp_s,0)
    e="🟢" if s=="BUY" else "🔴" if s=="SELL" else "🟡"
    bl2,_,sl2,_,_=calculate_levels(o,s)
    cols[i].metric(f"{e} ${t}",f"${o['close'][-1]:.0f}",f"Buy ${bl2} Sell ${sl2}")
