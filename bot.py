import os
import requests
import re
import xml.etree.ElementTree as ET
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# PASTE YOUR NEW TOKEN HERE AFTER YOU REVOKED THE OLD ONE
TOKEN = os.getenv("TELEGRAM_TOKEN") or "8715945496:AAHfhfZuk8B9veFv7pQwrPkKC7Xnw4UkCCY"

X_HANDLE = "mayur22sharma"

def get_ohlc(ticker):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=3mo"
        r = requests.get(url, headers={'User-Agent':'Mozilla/5.0'}, timeout=5).json()
        q = r['chart']['result'][0]['indicators']['quote'][0]
        data = [d for d in zip(q['open'], q['high'], q['low'], q['close']) if all(d)]
        return {'open':[d[0] for d in data],'high':[d[1] for d in data],'low':[d[2] for d in data],'close':[d[3] for d in data]}
    except:
        return {'open':[150]*60,'high':[152]*60,'low':[148]*60,'close':[150]*60}

def get_pe(ticker):
    try:
        url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}?modules=defaultKeyStatistics"
        r = requests.get(url, headers={'User-Agent':'Mozilla/5.0'}, timeout=5).json()
        return r['quoteSummary']['result'][0]['defaultKeyStatistics'].get('trailingPE',{}).get('raw')
    except: return None

def score_sentiment(text):
    pos=["bullish","growth","beat","record","strong","buy","surge","profit","breakout","cooking","long"]
    neg=["bearish","miss","down","cut","sell","weak","loss","risk","crash","overvalued","short"]
    t=text.lower(); return (sum(w in t for w in pos)-sum(w in t for w in neg)) / ((sum(w in t for w in pos)+sum(w in t for w in neg)) or 1)

def get_ceo_sentiment(ticker):
    ceo_map={"NVDA":"Jensen Huang","TSLA":"Elon Musk","AAPL":"Tim Cook","MSFT":"Satya Nadella","META":"Mark Zuckerberg","AMD":"Lisa Su"}
    ceo=ceo_map.get(ticker,"CEO")
    try:
        url=f"https://news.google.com/rss/search?q={ticker}+{ceo}&hl=en-US&gl=US&ceid=US:en"
        r=requests.get(url,timeout=5); root=ET.fromstring(r.content)
        heads=[i.find('title').text for i in root.findall('.//item')[:2]]
        sc=sum(score_sentiment(h) for h in heads)/len(heads) if heads else 0
        return ceo, heads[0][:100] if heads else "No news", sc
    except: return ceo,"No news",0

def calculate_levels(ohlc,sig):
    closes,highs,lows=ohlc['close'],ohlc['high'],ohlc['low']
    price=closes[-1]; support=min(lows[-20:]); resistance=max(highs[-20:])
    atr=sum(h-l for h,l in zip(highs[-14:],lows[-14:]))/14
    if sig=="BUY":
        bl=round(max(support,price*0.97),2); bh=round(price*1.005,2); sl=round(price*1.07,2); sh=round(min(resistance,price*1.12),2); st=round(bl*0.93,2)
    else:
        bl=round(support,2); bh=round(sum(closes[-20:])/20,2); sl=round(sum(closes[-50:])/50,2); sh=round(resistance,2); st=round(support*0.95,2)
    return bl,bh,sl,sh,st

def get_signal(ticker):
    o=get_ohlc(ticker); closes=o['close']; price=closes[-1]
    sma20=sum(closes[-20:])/20; sma50=sum(closes[-50:])/50
    ceo,news,ceo_sc=get_ceo_sentiment(ticker); pe=get_pe(ticker)
    g=[]; l=[]
    for i in range(1,15):
        ch=closes[-i]-closes[-i-1]; g.append(max(ch,0)); l.append(max(-ch,0))
    rsi=100-(100/(1+((sum(g)/14)/((sum(l)/14) or 0.01))))
    tech=1 if price>sma20>sma50 else -1 if price<sma20<sma50 else 0
    pe_sc=1 if pe and pe<20 else -1 if pe and pe>35 else 0
    final=(tech*0.5)+(pe_sc*0.2)+(ceo_sc*0.3)
    sig="BUY" if final>=0.3 else "SELL" if final<=-0.3 else "HOLD"
    conf=min(92,max(62,int(68+abs(final)*30)))
    bl,bh,sl,sh,st=calculate_levels(o,sig)
    return sig,conf,pe,ceo,news,rsi,price,bl,bh,sl,sh,st

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Mayur AI Trading Bot Live\n\n/signal NVDA - buy/sell levels\n/ceo TSLA\n/watchlist")

async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ticker=(context.args[0] if context.args else "NVDA").upper()
    await update.message.reply_text(f"Analyzing ${ticker}...")
    sig,conf,pe,ceo,news,rsi,price,bl,bh,sl,sh,st=get_signal(ticker)
    e="🟢" if sig=="BUY" else "🔴" if sig=="SELL" else "🟡"
    msg=f"{e} MAYUR TAKE: {sig} ${ticker} | {conf}%\nBuy ${bl}-${bh} | Sell ${sl}-${sh} | Stop ${st}\nPrice ${price:.2f} PE {pe or 'N/A'} RSI {rsi:.0f}\nCEO {ceo}: {news}"
    await update.message.reply_text(msg)

async def ceo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t=(context.args[0] if context.args else "NVDA").upper()
    ceo,news,sc=get_ceo_sentiment(t)
    await update.message.reply_text(f"{ceo} on ${t}:\n{news}\nScore {sc:+.2f}")

async def watchlist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg="Watchlist:\n"
    for t in ["NVDA","TSLA","AAPL","MSFT","AMD"]:
        s,c,_,_,_,_,pr,bl,_,sl,_,_=get_signal(t)
        e="🟢" if s=="BUY" else "🔴" if s=="SELL" else "🟡"
        msg+=f"{e} ${t} ${pr:.0f} Buy ${bl} Sell ${sl}\n"
    await update.message.reply_text(msg)

def main():
    app=Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("signal",signal_cmd))
    app.add_handler(CommandHandler("ceo",ceo_cmd))
    app.add_handler(CommandHandler("watchlist",watchlist_cmd))
    print("Bot running...")
    app.run_polling()

if __name__=="__main__":
    main()
