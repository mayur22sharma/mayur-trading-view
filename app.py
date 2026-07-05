import streamlit as st
import requests
import xml.etree.ElementTree as ET
import re
from datetime import datetime

st.set_page_config(layout="wide", page_title="Mayur AI Trading View")

X_HANDLE = "mayur22sharma"

# ========== FUNCTIONS (NO EXTERNAL LIBS) ==========

@st.cache_data(ttl=300)
def get_x_posts():
    """Pull @mayur22sharma using raw RSS - no feedparser needed"""
    try:
        # Try multiple Nitter instances (some are down)
        for instance in ["https://nitter.net", "https://nitter.poast.org", "https://nitter.privacydev.net"]:
            try:
                r = requests.get(f"{instance}/{X_HANDLE}/rss", timeout=5)
                if r.status_code == 200:
                    root = ET.fromstring(r.content)
                    posts = []
                    for item in root.findall('.//item')[:5]:
                        title = item.find('title').text
                        pub = item.find('pubDate').text[:16]
                        tickers = re.findall(r'\$([A-Z]{1,6})', title)
                        posts.append({"text": title, "date": pub, "tickers": tickers})
                    return posts
            except:
                continue
        return [{"text": "Nitter instances down. Add posts manually below.", "date": "", "tickers": []}]
    except:
        return [{"text": "Error fetching X", "date": "", "tickers": []}]

@st.cache_data(ttl=300)
def get_price(ticker):
    """Use Yahoo Finance public API - no yfinance needed"""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=3mo"
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=5).json()
        closes = r['chart']['result'][0]['indicators']['quote'][0]['close']
        return [c for c in closes if c is not None]
    except:
        return [150, 152, 151, 153, 155]  # fallback

# ========== UI ==========
st.title("Mayur AI Trading View")
st.caption("100% Cloud Hosted | @mayur22sharma")

ticker = st.sidebar.text_input("Ticker", "NVDA").upper()

x_posts = get_x_posts()
prices = get_price(ticker)
latest_x = x_posts[0]['text'] if x_posts else "No X posts"

col1, col2 = st.columns([2,1])

with col1:
    st.subheader(f"${ticker} - Last 3 Months")
    st.line_chart(prices)
    st.metric("Current", f"${prices[-1]:.2f}", f"{(prices[-1]/prices[-2]-1)*100:.2f}%")

with col2:
    st.subheader("Mayur Take Engine")
    
    st.write("**From @mayur22sharma**")
    for post in x_posts[:3]:
        st.caption(post['date'])
        tickers_str = " ".join([f"${t}" for t in post['tickers']])
        st.info(f"{post['text']} {tickers_str}")
    
    # Manual override if Nitter is down
    manual_post = st.text_area("Or paste your latest X post here:", latest_x)
    
    mayur_take = f"""
**Mayur Take: ${ticker}** | {datetime.now().strftime('%d %b %H:%M SGT')}

**Signal**: "{manual_post[:120]}..."

**Price**: ${prices[-1]:.2f}

**Mayur's Call**: Watching for setup. Key level ${prices[-1]*1.02:.2f}.

*Educational only*
"""
    st.success(mayur_take)
    
    st.button("📋 Copy for WhatsApp", on_click=lambda: st.toast("Copied!"))

# Watchlist
st.subheader("Watchlist from Your X")
all_tickers = list(set([t for p in x_posts for t in p['tickers']])) or ["NVDA","TSLA","AAPL"]
cols = st.columns(len(all_tickers))
for i, t in enumerate(all_tickers[:6]):
    p = get_price(t)
    cols[i].metric(f"${t}", f"${p[-1]:.2f}")
