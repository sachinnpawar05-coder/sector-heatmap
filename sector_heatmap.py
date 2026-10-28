import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from plotly.colors import sample_colorscale
import re
import urllib.request, urllib.parse
import xml.etree.ElementTree as ET

st.set_page_config(page_title="Sector Heatmap Scanner", layout="wide")
st.title("📊 NSE Sector Heatmap Scanner")

SECTORS = {
    "Bank": "^NSEBANK", "IT": "^CNXIT", "Pharma": "^CNXPHARMA", "Auto": "^CNXAUTO",
    "FMCG": "^CNXFMCG", "Metal": "^CNXMETAL", "Realty": "^CNXREALTY",
    "Energy": "^CNXENERGY", "PSU Bank": "^CNXPSUBANK", "Media": "^CNXMEDIA",
    "Infra": "^CNXINFRA", "Fin Services": "NIFTY_FIN_SERVICE.NS",
}
STOCKS = {k: v.split() for k, v in {
    "Bank": "HDFCBANK ICICIBANK SBIN KOTAKBANK AXISBANK INDUSINDBK BANKBARODA PNB FEDERALBNK IDFCFIRSTB AUBANK CANBK",
    "IT": "TCS INFY HCLTECH WIPRO TECHM LTIM PERSISTENT COFORGE MPHASIS OFSS",
    "Pharma": "SUNPHARMA CIPLA DRREDDY DIVISLAB LUPIN AUROPHARMA TORNTPHARM ZYDUSLIFE ALKEM MANKIND GLENMARK BIOCON LAURUSLABS IPCALAB ABBOTINDIA",
    "Auto": "M&M MARUTI TMPV BAJAJ-AUTO EICHERMOT HEROMOTOCO TVSMOTOR ASHOKLEY BOSCHLTD BHARATFORG MRF BALKRISIND SONACOMS TIINDIA EXIDEIND",
    "FMCG": "ITC HINDUNILVR NESTLEIND BRITANNIA TATACONSUM VBL GODREJCP DABUR MARICO COLPAL UNITDSPR PATANJALI RADICO EMAMILTD",
    "Metal": "TATASTEEL JSWSTEEL HINDALCO VEDL JINDALSTEL NMDC SAIL ADANIENT APLAPOLLO HINDZINC NATIONALUM JSL",
    "Realty": "DLF GODREJPROP LODHA OBEROIRLTY PRESTIGE PHOENIXLTD BRIGADE SOBHA",
    "Energy": "RELIANCE ONGC NTPC POWERGRID COALINDIA BPCL IOC GAIL TATAPOWER ADANIGREEN ADANIPOWER OIL PETRONET HINDPETRO",
    "PSU Bank": "SBIN BANKBARODA PNB CANBK UNIONBANK INDIANB BANKINDIA MAHABANK IOB UCOBANK CENTRALBK PSB",
    "Media": "ZEEL SUNTV PVRINOX NETWORK18 SAREGAMA NAZARA DBCORP TIPSMUSIC",
    "Infra": "LT BHARTIARTL ULTRACEMCO ADANIPORTS GRASIM INDIGO INDUSTOWER DLF IRCTC CONCOR CUMMINSIND SIEMENS ABB BHEL HAVELLS NHPC JSWENERGY KEC",
    "Fin Services": "HDFCBANK ICICIBANK BAJFINANCE BAJAJFINSV SBIN KOTAKBANK AXISBANK HDFCLIFE SBILIFE CHOLAFIN SHRIRAMFIN JIOFIN MUTHOOTFIN PFC RECLTD ICICIGI HDFCAMC SBICARD",
}.items()}
PERIODS = {"1D": 1, "1W": 5, "1M": 21, "3M": 63, "6M": 126, "1Y": 252}


@st.cache_data(ttl=900)
def load(tickers):
    df = yf.download(list(tickers), period="2y", auto_adjust=True, progress=False)["Close"]
    return df.dropna(how="all")


def ret(s, n):
    s = s.dropna()
    return (s.iloc[-1] / s.iloc[-1 - n] - 1) * 100 if len(s) > n else float("nan")


period = st.radio("Period", list(PERIODS), index=1, horizontal=True)
n = PERIODS[period]

px_df = load(tuple(SECTORS.values()) + ("^NSEI",))
nifty = px_df["^NSEI"]

rows = []
for name, t in SECTORS.items():
    if t not in px_df or px_df[t].dropna().empty:
        continue
    s = px_df[t].dropna()
    rs = (s / nifty).dropna()
    rs_ratio = 100 * rs / rs.rolling(50).mean()
    rs_mom = 100 * rs_ratio / rs_ratio.shift(10)
    rr, rm = rs_ratio.iloc[-1], rs_mom.iloc[-1]
    quad = ("Leading" if rr >= 100 and rm >= 100 else "Weakening" if rr >= 100
            else "Improving" if rm >= 100 else "Lagging")
    rows.append({"Sector": name, "Return %": round(ret(s, n), 2),
                 "vs Nifty %": round(ret(s, n) - ret(nifty, n), 2),
                 "Above 50DMA": s.iloc[-1] > s.rolling(50).mean().iloc[-1],
                 "Above 200DMA": s.iloc[-1] > s.rolling(200).mean().iloc[-1],
                 "RS Ratio": round(rr, 1), "RS Mom": round(rm, 1), "Phase": quad})
df = pd.DataFrame(rows).dropna(subset=["Return %"])

mode = st.radio("Color by", ["Return %", "vs Nifty %"], horizontal=True)
phase = df.set_index("Sector")["Phase"].to_dict()

all_tk = sorted({s + ".NS" for v in STOCKS.values() for s in v})
sp = load(tuple(all_tk))
nret = ret(nifty, n)

recs = []
for sec, syms in STOCKS.items():
    for s in syms:
        c = s + ".NS"
        if c not in sp or sp[c].dropna().empty:
            continue
        x = sp[c].dropna()
        r = ret(x, n)
        if pd.isna(r):
            continue
        x52 = x.tail(252)
        hi, lo, last = x52.max(), x52.min(), x.iloc[-1]
        recs.append({"Sector": sec, "Stock": s, "Price": round(last, 2),
                     "52W High": round(hi, 2), "52W Low": round(lo, 2),
                     "% from High": round((last / hi - 1) * 100, 1),
                     "% above Low": round((last / lo - 1) * 100, 1),
                     "Return %": round(r, 2),
                     "Ret": round(r - nret if mode == "vs Nifty %" else r, 2)})
sdf = pd.DataFrame(recs)

# ---- Sector signals (4 lists)
st.subheader("Sector signals")
strong_now = df.nlargest(3, "Return %")["Sector"].tolist()
weak_now = df.nsmallest(3, "Return %")["Sector"].tolist()
up = df[df["Phase"].isin(["Improving", "Leading"])].nlargest(3, "RS Mom")["Sector"].tolist()
down = df[df["Phase"].isin(["Weakening", "Lagging"])].nsmallest(3, "RS Mom")["Sector"].tolist()
c1, c2 = st.columns(2)
c1.success("🟢 Abhi strong: " + ", ".join(strong_now))
c2.error("🔴 Abhi weak: " + ", ".join(weak_now))
c3, c4 = st.columns(2)
c3.info("🚀 Aage strong ho sakte hain: " + (", ".join(up) or "koi nahi"))
c4.warning("⚠️ Aage weak ho sakte hain: " + (", ".join(down) or "koi nahi"))

# ---- Heat tiles: sector -> stock -> line chart
ss = st.session_state
ss.setdefault("sel_sec", None)
ss.setdefault("sel_stk", None)


def go_sec(x):
    ss.sel_sec, ss.sel_stk = x, None


def go_stk(x):
    ss.sel_stk = None if ss.sel_stk == x else x


def go_back():
    ss.sel_sec, ss.sel_stk = None, None


css = []


def tile(label, key, v, lim, cb, arg):
    t = min(max((v + lim) / (2 * lim), 0), 1)
    bg = sample_colorscale("RdYlGn", [t])[0]
    fg = "#fff" if (t < 0.15 or t > 0.82) else "#111"
    k = re.sub(r"\W", "_", key)
    css.append(f".st-key-{k} button{{background:{bg} !important;border:1px solid rgba(0,0,0,.35) !important;"
               f"min-height:66px;justify-content:flex-start;text-align:left}}"
               f".st-key-{k} button p,.st-key-{k} button strong{{color:{fg} !important;text-align:left}}")
    st.button(label, key=k, on_click=cb, args=(arg,), use_container_width=True)


@st.cache_data(ttl=900)
def load_ohlc(tk):
    d = yf.download(tk, period="2y", auto_adjust=True, progress=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    return d.dropna(subset=["Close"])


@st.cache_data(ttl=300)
def load_intra(tk, period, interval):
    d = yf.download(tk, period=period, interval=interval, auto_adjust=True, progress=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    d = d.dropna()
    if not d.empty:
        idx = d.index.tz_localize("UTC") if d.index.tz is None else d.index
        d.index = idx.tz_convert("Asia/Kolkata")
    return d


INTRA = {"1D": ("1d", "5m"), "1W": ("5d", "15m")}


def render_chart(stk):
    st.markdown(f"#### 📈 {stk}")
    rng = st.radio("Range", ["1D", "1W", "1M", "3M", "6M", "1Y"], index=4, horizontal=True, key="chart_rng")
    kind = st.radio("Chart type", ["Line", "Candle"], horizontal=True, key="chart_kind")
    intraday = rng in INTRA
    dd = load_ohlc(stk + ".NS")
    if dd.empty:
        st.warning("Is stock ka data nahi mila.")
        return
    if intraday:
        v = load_intra(stk + ".NS", *INTRA[rng])
        if v.empty:
            st.warning("Intraday data nahi mila (market band ho sakta hai). 1M ya uske upar ka range chuno.")
            return
        ts = v.index[-1].strftime("%d %b %Y, %H:%M") + " IST"
    else:
        days = {"1M": 21, "3M": 63, "6M": 126, "1Y": 252}[rng]
        dd["MA50"] = dd["Close"].rolling(50).mean()
        dd["MA200"] = dd["Close"].rolling(200).mean()
        v = dd.tail(days)
        ts = v.index[-1].strftime("%d %b %Y") + " (close)"
    last = float(v["Close"].iloc[-1])
    prev = float(dd["Close"].iloc[-2]) if len(dd) > 1 else last
    st.markdown(f"**₹{last:,.2f}** ({(last / prev - 1) * 100:+.2f}%) · 🕒 {ts}")

    cf = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.75, 0.25],
                       vertical_spacing=0.03)
    if kind == "Line":
        cf.add_trace(go.Scatter(x=v.index, y=v["Close"], name=stk, line=dict(width=2.5)), row=1, col=1)
    else:
        cf.add_trace(go.Candlestick(x=v.index, open=v["Open"], high=v["High"], low=v["Low"],
                                    close=v["Close"], name=stk), row=1, col=1)
    if not intraday:
        hi, lo = dd["Close"].tail(252).max(), dd["Close"].tail(252).min()
        cf.add_trace(go.Scatter(x=v.index, y=v["MA50"], name="50 DMA", line=dict(width=1.5)), row=1, col=1)
        cf.add_trace(go.Scatter(x=v.index, y=v["MA200"], name="200 DMA", line=dict(width=1.5)), row=1, col=1)
        cf.add_hline(y=hi, line_dash="dot", line_color="green", annotation_text=f"52W High {hi:.1f}", row=1, col=1)
        cf.add_hline(y=lo, line_dash="dot", line_color="red", annotation_text=f"52W Low {lo:.1f}", row=1, col=1)
    cf.add_trace(go.Bar(x=v.index, y=v["Volume"], name="Volume", marker_color="gray"), row=2, col=1)
    breaks = [dict(bounds=["sat", "mon"])]
    if intraday:
        breaks.append(dict(bounds=[15.5, 9.25], pattern="hour"))
    cf.update_xaxes(rangebreaks=breaks, showspikes=True, spikemode="across", spikesnap="cursor",
                    spikethickness=1, spikedash="dot", spikecolor="#999",
                    hoverformat="%d %b %Y, %H:%M" if intraday else "%d %b %Y")
    cf.update_yaxes(showspikes=True, spikemode="across", spikesnap="cursor",
                    spikethickness=1, spikedash="dot", spikecolor="#999")
    cf.update_traces(hovertemplate="₹%{y:.2f}", selector=dict(type="scatter"))
    cf.update_traces(hovertemplate="%{y:,.0f}", selector=dict(type="bar"))
    cf.update_layout(height=500, xaxis_rangeslider_visible=False, margin=dict(t=10, l=0, r=0, b=0),
                     legend=dict(orientation="h", y=1.04), hovermode="x unified", dragmode=False)
    st.plotly_chart(cf, use_container_width=True, config={"displayModeBar": False})


def render_sector_chart(sec):
    tk = SECTORS[sec]
    rng = st.radio("Range", ["1D", "1W", "1M", "3M", "6M", "1Y"], index=2, horizontal=True, key="sch_rng")
    cmp_on = st.checkbox("Nifty 50 se compare karo (dono 100 se shuru)", key="sch_cmp")
    intraday = rng in INTRA
    d = load_ohlc(tk)
    if d.empty:
        st.warning("Is sector index ka data yfinance se nahi mila.")
        return
    if intraday:
        v = load_intra(tk, *INTRA[rng])
        if v.empty:
            st.warning("Intraday data nahi mila (market band ho sakta hai). 1M ya uske upar ka range chuno.")
            return
        ts = v.index[-1].strftime("%d %b %Y, %H:%M") + " IST"
    else:
        days = {"1M": 21, "3M": 63, "6M": 126, "1Y": 252}[rng]
        d["MA50"] = d["Close"].rolling(50).mean()
        d["MA200"] = d["Close"].rolling(200).mean()
        v = d.tail(days)
        ts = v.index[-1].strftime("%d %b %Y") + " (close)"
    last = float(v["Close"].iloc[-1])
    prev = float(d["Close"].iloc[-2]) if len(d) > 1 else last
    st.markdown(f"**{last:,.2f}** ({(last / prev - 1) * 100:+.2f}%) · 🕒 {ts}")
    cf = go.Figure()
    if cmp_on:
        nraw = load_intra("^NSEI", *INTRA[rng]) if intraday else load_ohlc("^NSEI")
        nf = nraw["Close"].reindex(v.index).ffill().bfill()
        cf.add_trace(go.Scatter(x=v.index, y=v["Close"] / v["Close"].iloc[0] * 100, name=sec,
                                line=dict(width=2.5)))
        cf.add_trace(go.Scatter(x=v.index, y=nf / nf.iloc[0] * 100, name="Nifty 50",
                                line=dict(width=1.8, dash="dot")))
        cf.add_hline(y=100, line_dash="dot", line_color="#999")
    else:
        cf.add_trace(go.Scatter(x=v.index, y=v["Close"], name=sec, line=dict(width=2.5)))
        if not intraday:
            hi, lo = d["Close"].tail(252).max(), d["Close"].tail(252).min()
            cf.add_trace(go.Scatter(x=v.index, y=v["MA50"], name="50 DMA", line=dict(width=1.5)))
            cf.add_trace(go.Scatter(x=v.index, y=v["MA200"], name="200 DMA", line=dict(width=1.5)))
            cf.add_hline(y=hi, line_dash="dot", line_color="green", annotation_text=f"52W High {hi:,.0f}")
            cf.add_hline(y=lo, line_dash="dot", line_color="red", annotation_text=f"52W Low {lo:,.0f}")
    breaks = [dict(bounds=["sat", "mon"])]
    if intraday:
        breaks.append(dict(bounds=[15.5, 9.25], pattern="hour"))
    cf.update_xaxes(rangebreaks=breaks, showspikes=True, spikemode="across", spikesnap="cursor",
                    spikethickness=1, spikedash="dot", spikecolor="#999",
                    hoverformat="%d %b %Y, %H:%M" if intraday else "%d %b %Y")
    cf.update_yaxes(showspikes=True, spikemode="across", spikesnap="cursor",
                    spikethickness=1, spikedash="dot", spikecolor="#999")
    cf.update_traces(hovertemplate="%{y:,.2f}")
    cf.update_layout(height=420, margin=dict(t=10, l=0, r=0, b=0), legend=dict(orientation="h", y=1.08),
                     hovermode="x unified", dragmode=False)
    st.plotly_chart(cf, use_container_width=True, config={"displayModeBar": False})


GLOBAL = {"S&P 500": "^GSPC", "Nasdaq": "^IXIC", "Hang Seng": "^HSI", "Brent crude": "BZ=F",
          "Copper": "HG=F", "USD/INR": "INR=X", "US 10Y yield": "^TNX", "Dollar index": "DX-Y.NYB",
          "India VIX": "^INDIAVIX"}
# (factor, +1 agar badhna sector ke liye achha, -1 agar badhna sector ke liye bura)
SENS = {
    "IT": [("Nasdaq", 1), ("USD/INR", 1), ("US 10Y yield", -1)],
    "Pharma": [("USD/INR", 1), ("S&P 500", 1)],
    "Bank": [("S&P 500", 1), ("Dollar index", -1), ("India VIX", -1)],
    "PSU Bank": [("S&P 500", 1), ("Dollar index", -1), ("India VIX", -1)],
    "Fin Services": [("S&P 500", 1), ("Dollar index", -1), ("India VIX", -1)],
    "Auto": [("Brent crude", -1), ("Copper", -1)],
    "FMCG": [("Brent crude", -1)],
    "Metal": [("Copper", 1), ("Hang Seng", 1), ("Dollar index", -1)],
    "Realty": [("US 10Y yield", -1), ("India VIX", -1)],
    "Energy": [("Brent crude", 1)],
    "Media": [("India VIX", -1)],
    "Infra": [("US 10Y yield", -1), ("Copper", -1), ("Brent crude", -1)],
}
WHY = {
    "IT": "IT ki kamai ka bada hissa US se aata hai, aur kamzor rupaya revenue badhata hai. US yields badhne se tech valuations par dabav aata hai.",
    "Pharma": "Pharma ka bada export US ko hai, to kamzor rupaya faydemand hota hai.",
    "Bank": "Global risk mood, dollar ki taqat aur VIX se FPI flows prabhavit hote hain, jo bank stocks ko sabse zyada hilate hain.",
    "PSU Bank": "Global risk mood, dollar ki taqat aur VIX se FPI flows prabhavit hote hain.",
    "Fin Services": "NBFC aur financials FPI flows aur interest rate mood par nirbhar hain.",
    "Auto": "Crude aur copper mehnge hone se input cost badhti hai, jo margin par dabav daalti hai.",
    "FMCG": "Crude mehnga hone se packaging aur freight cost badhti hai.",
    "Metal": "Metal prices global demand (China) aur dollar se chalte hain.",
    "Realty": "Interest rate mood (US yields, VIX) se real estate ki demand aur valuation prabhavit hoti hai.",
    "Energy": "Crude mehnga hone se upstream companies (jaise ONGC) ko fayda, par refining aur marketing wali ko kabhi nuksan.",
    "Media": "Ad spending aur market mood se prabhavit.",
    "Infra": "Input costs (copper, crude) aur interest rates infra projects ki margin aur financing par asar daalte hain.",
}
NEWSQ = {
    "Bank": "India government RBI policy banking sector",
    "IT": "India IT sector US tariff H-1B policy",
    "Pharma": "India pharma sector government policy tariff USFDA",
    "Auto": "India auto sector government policy GST EV",
    "FMCG": "India FMCG sector government policy GST rural demand",
    "Metal": "India steel metal sector government duty policy",
    "Realty": "India real estate sector government policy RBI rate",
    "Energy": "India oil gas sector government policy crude",
    "PSU Bank": "India PSU banks government policy",
    "Media": "India media entertainment sector government policy",
    "Infra": "India infrastructure government capex policy",
    "Fin Services": "India NBFC financial sector SEBI RBI policy",
}


@st.cache_data(ttl=900)
def load_global():
    g = yf.download(list(GLOBAL.values()), period="1mo", auto_adjust=True, progress=False)["Close"]
    return g.ffill()


@st.cache_data(ttl=1800)
def fetch_news(q, n=6):
    url = ("https://news.google.com/rss/search?q=" + urllib.parse.quote(q + " when:7d")
           + "&hl=en-IN&gl=IN&ceid=IN:en")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(urllib.request.urlopen(req, timeout=10).read())
        out = []
        for it in root.iter("item"):
            title = (it.findtext("title") or "").replace("[", "(").replace("]", ")")
            out.append((title, it.findtext("link") or "", (it.findtext("pubDate") or "")[:16]))
            if len(out) >= n:
                break
        return out
    except Exception:
        return []


def global_section(sec):
    try:
        g = load_global()
    except Exception:
        return "**Global cues:** data abhi nahi mila."
    rows, net = ["| Factor | 1D | 1W | Is sector par asar |", "|---|---|---|---|"], 0
    for name, sign in SENS.get(sec, []):
        tk = GLOBAL[name]
        if tk not in g:
            continue
        x = g[tk].dropna()
        if len(x) < 6:
            continue
        c1, cw = (x.iloc[-1] / x.iloc[-2] - 1) * 100, (x.iloc[-1] / x.iloc[-6] - 1) * 100
        eff = cw * sign
        tag = "✅ Tailwind" if eff >= 1 else "⚠️ Headwind" if eff <= -1 else "➖ Neutral"
        net += 1 if eff >= 1 else -1 if eff <= -1 else 0
        rows.append(f"| {name} | {c1:+.2f}% | {cw:+.2f}% | {tag} |")
    if len(rows) == 2:
        return "**Global cues:** is sector ke liye data nahi mila."
    verdict = ("Global cues is sector ke liye halke supportive hain." if net > 0 else
               "Global cues is sector par dabav daal rahe hain." if net < 0 else
               "Global cues mixed ya neutral hain.")
    return (f"**Global market ka asar (pichle 1 hafte ke hisaab se)**\n\n" + "\n".join(rows)
            + f"\n\n{verdict} _Kyun:_ {WHY.get(sec, '')}")


def news_section(sec):
    items = fetch_news(NEWSQ.get(sec, f"India {sec} sector government policy"))
    if not items:
        return "**Sarkari / policy news:** abhi news nahi mil payi."
    lines = [f"- [{t}]({u}) · {d}" for t, u, d in items]
    return ("**Sarkari / policy news (pichle 7 din ki headlines)**\n\n" + "\n".join(lines)
            + "\n\n_Headlines Google News se automatically aayi hain, hum unka asar khud nahi nikalte. "
              "Link kholke padho aur khud samjho._")


def _f(v, d=1):
    return "NA" if v is None or pd.isna(v) else f"{v:+.{d}f}%"


def build_report(sec):
    t = SECTORS[sec]
    if t not in px_df or px_df[t].dropna().empty:
        return None
    s = px_df[t].dropna()
    ni = nifty.dropna()
    last = float(s.iloc[-1])
    ma50, ma200 = s.rolling(50).mean().iloc[-1], s.rolling(200).mean().iloc[-1]
    h52, l52 = s.tail(252).max(), s.tail(252).min()
    from_h, above_l = (last / h52 - 1) * 100, (last / l52 - 1) * 100
    if last > ma50 > ma200:
        trend = "Uptrend: index 50 DMA aur 200 DMA dono ke upar hai, aur 50 DMA > 200 DMA."
    elif last < ma50 < ma200:
        trend = "Downtrend: index 50 DMA aur 200 DMA dono ke neeche hai."
    else:
        trend = "Mixed / badalta hua trend: price DMA lines ke beech ya ulte order mein hai."

    tbl = ["| Period | Sector | Nifty 50 | Farak |", "|---|---|---|---|"]
    diffs = {}
    for p, n_ in PERIODS.items():
        a, b = ret(s, n_), ret(ni, n_)
        diffs[p] = a - b
        tbl.append(f"| {p} | {_f(a, 2)} | {_f(b, 2)} | {_f(diffs[p], 2)} |")

    syms = [x for x in STOCKS[sec] if x + ".NS" in sp and not sp[x + ".NS"].dropna().empty]
    N = len(syms)
    a50 = a200 = up1m = up3m = nh = nl = 0
    for x in syms:
        c = sp[x + ".NS"].dropna()
        c52 = c.tail(252)
        a50 += int(c.iloc[-1] > c.rolling(50).mean().iloc[-1])
        a200 += int(c.iloc[-1] > c.rolling(200).mean().iloc[-1])
        up1m += int(ret(c, 21) > 0)
        up3m += int(ret(c, 63) > 0)
        nh += int(c.iloc[-1] >= c52.max() * 0.95)
        nl += int(c.iloc[-1] <= c52.min() * 1.10)
    p50 = a50 / N * 100 if N else float("nan")
    p200 = a200 / N * 100 if N else float("nan")

    dfi = df.set_index("Sector")
    ph, rr, rm = ("NA", float("nan"), float("nan"))
    if sec in dfi.index:
        ph, rr, rm = dfi.loc[sec, "Phase"], dfi.loc[sec, "RS Ratio"], dfi.loc[sec, "RS Mom"]

    g = sdf[sdf["Sector"] == sec].sort_values("Ret", ascending=False)
    lead = ", ".join(f"{r.Stock} ({r.Ret:+.1f}%)" for r in g.head(3).itertuples())
    lag = ", ".join(f"{r.Stock} ({r.Ret:+.1f}%)" for r in g.tail(3).iloc[::-1].itertuples())

    checks = [("Index 50 DMA ke upar", last > ma50), ("Index 200 DMA ke upar", last > ma200),
              ("3M mein Nifty se behtar", diffs["3M"] > 0), ("1M mein Nifty se behtar", diffs["1M"] > 0),
              ("RS momentum 100 ke upar", rm >= 100), ("50 DMA ke upar stocks 60% ya zyada", p50 >= 60)]
    score = sum(1 for _, ok in checks if ok)

    obs = []
    if diffs["3M"] > 0 and ret(s, 5) < 0:
        obs.append("3M mein market se behtar, par pichle 1 hafte mein kamzor. Ye pullback ya thakaan ka sanket ho sakta hai.")
    if all(diffs[p] > 0 for p in ["1W", "1M", "3M"]):
        obs.append("1W, 1M aur 3M teeno mein Nifty se behtar. Short aur medium term dono mein relative strength hai.")
    if all(diffs[p] < 0 for p in ["1W", "1M", "3M"]):
        obs.append("1W, 1M aur 3M teeno mein Nifty se kamzor. Relative weakness saaf hai.")
    if p50 >= 70:
        obs.append("Zyada tar stocks 50 DMA ke upar hain, yaani tezi sirf ek-do stocks tak seemit nahi, broad hai.")
    elif p50 < 40:
        obs.append("Kam stocks 50 DMA ke upar hain. Sector index ki chaal kuch hi bade stocks par tiki ho sakti hai.")
    if ph == "Improving":
        obs.append("Phase Improving: RS momentum badh raha hai par ratio abhi 100 se neeche. Turnaround ka shuruati daur ho sakta hai, confirm hona baaki.")
    elif ph == "Leading":
        obs.append("Phase Leading: ratio aur momentum dono 100 ke upar. Market se aage chal raha hai.")
    elif ph == "Weakening":
        obs.append("Phase Weakening: ratio 100 ke upar hai par momentum ghat raha hai. Tezi thandi pad rahi ho sakti hai.")
    elif ph == "Lagging":
        obs.append("Phase Lagging: ratio aur momentum dono 100 ke neeche. Market se peeche hai.")
    if from_h > -3:
        obs.append("Index 52W high ke bahut paas hai. Ye breakout aur resistance dono ka zone ho sakta hai.")
    if ret(s, 1) <= -1.5:
        obs.append(f"Pichle din index {_f(ret(s, 1), 2)} gira. Short term mein bikwali ka dabav hai.")
    if not obs:
        obs.append("Koi khaas extreme signal nahi dikh raha, sector mixed chaal mein hai.")

    out = [f"## {sec} sector analysis ({s.index[-1].strftime('%d %b %Y')})",
           f"**Trend:** {trend}",
           f"**Index:** {last:,.2f} · 52W High se {from_h:.1f}% neeche · 52W Low se +{above_l:.1f}% upar",
           "**Returns vs Nifty 50**\n\n" + "\n".join(tbl),
           f"**Relative strength (RRG):** phase **{ph}**, RS Ratio {rr:.1f}, RS Momentum {rm:.1f}",
           f"**Breadth ({N} stocks):** {p50:.0f}% stocks 50 DMA ke upar, {p200:.0f}% 200 DMA ke upar. "
           f"1M mein {up1m}/{N} aur 3M mein {up3m}/{N} stocks positive. "
           f"{nh} stocks 52W high ke 5% ke andar, {nl} stocks 52W low ke 10% ke andar.",
           f"**Leaders ({period}):** {lead}\n\n**Laggards ({period}):** {lag}",
           f"**Signal checklist: {score}/6**\n\n" + "\n".join(f"- {'✅' if ok else '❌'} {name}" for name, ok in checks),
           "**Observations**\n\n" + "\n".join(f"- {o}" for o in obs),
           global_section(sec),
           news_section(sec),
           "_Ye report sirf data par based automatic summary hai, investment advice ya recommendation nahi hai. "
           "Data yfinance se hai aur late ya galat ho sakta hai. Trade se pehle apna analysis karo._"]
    return "\n\n".join(out)


sec_avg = sdf.groupby("Sector")["Ret"].mean().sort_values(ascending=False)
if ss.sel_sec is None:
    st.caption("👆 Sector par tap karo, uske saare stocks khulenge. Phir stock par tap karo, uska line chart khulega.")
    slim = max(float(sec_avg.abs().quantile(0.9)), 3)
    for sec, avg in sec_avg.items():
        tile(f"**{sec} · {phase.get(sec, '')}**  \n{avg:+.1f}% ({period})", f"sec_{sec}", avg, slim, go_sec, sec)
else:
    sec = ss.sel_sec
    st.button("⬅ Sab sectors", on_click=go_back, key="back_btn")
    g = sdf[sdf["Sector"] == sec].sort_values("Ret", ascending=False)
    st.markdown(f"### {sec} · {phase.get(sec, '')}")
    with st.expander(f"📈 {sec} index chart", expanded=True):
        render_sector_chart(sec)
    with st.expander(f"📄 {sec} analysis report"):
        rep = build_report(sec)
        if rep:
            st.markdown(rep)
            st.download_button("⬇ Report download (.md)", rep, file_name=f"{sec.replace(' ', '_')}_report.md",
                               key=f"dl_{sec}")
        else:
            st.warning("Is sector index ka data nahi mila, report nahi ban saki.")
    st.caption("Stock ke box par tap karo, uska chart usi box ke neeche khulega. Band karne ke liye dobara tap karo.")
    tlim = max(float(g["Ret"].abs().quantile(0.9)), 3)
    for _, r in g.iterrows():
        tile(f"**{r.Stock}**  ₹{r.Price:,.2f}  \n{r.Ret:+.1f}% ({period}) · H {r['% from High']:.0f}% · L +{r['% above Low']:.0f}%",
             f"stk_{sec}_{r.Stock}", r.Ret, tlim, go_stk, r.Stock)
        if ss.sel_stk == r.Stock:
            render_chart(r.Stock)
if css:
    st.markdown("<style>" + "".join(css) + "</style>", unsafe_allow_html=True)

st.subheader("Sector ranking")
st.dataframe(df.drop(columns="size", errors="ignore").sort_values("Return %", ascending=False),
             use_container_width=True, hide_index=True)

# ---- Stock table with 52W high/low
st.subheader("Stocks: 52 week High / Low")
pick = st.selectbox("Sector chuno", ["Sab"] + list(STOCKS))
sort_by = st.selectbox("Sort by", ["% from High", "% above Low", "Return %"])
t = sdf if pick == "Sab" else sdf[sdf["Sector"] == pick]
order = st.radio("Order", ["Ascending (kam se zyada)", "Descending (zyada se kam)"], horizontal=True)
st.dataframe(t.drop(columns="Ret").sort_values(sort_by, ascending=order.startswith("Asc")),
             use_container_width=True, hide_index=True)
st.caption("52W High/Low pichle 1 saal ke closing prices se nikle hain (intraday high/low thoda alag ho sakta hai). "
           "% from High = high se kitna neeche, % above Low = low se kitna upar.")

st.caption("Data: yfinance (15 min cache). Sirf analysis ke liye, investment advice nahi.")
