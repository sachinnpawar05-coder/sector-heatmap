import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from plotly.colors import sample_colorscale
import re

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
    return d.dropna()


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


INTRA = {"1D": ("1d", "5m"), "5D": ("5d", "15m")}


def render_chart(stk):
    st.markdown(f"#### 📈 {stk}")
    rng = st.radio("Range", ["1D", "5D", "1M", "3M", "6M", "1Y"], index=4, horizontal=True, key="chart_rng")
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
    st.caption("Stock ke box par tap karo, uska chart usi box ke neeche khulega. Band karne ke liye dobara tap karo.")
    tlim = max(float(g["Ret"].abs().quantile(0.9)), 3)
    for _, r in g.iterrows():
        tile(f"**{r.Stock}**  {r.Ret:+.1f}% ({period})  \nH {r['% from High']:.0f}% · L +{r['% above Low']:.0f}%",
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
