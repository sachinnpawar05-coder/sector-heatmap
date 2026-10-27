import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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
PERIODS = {"1D": 1, "1W": 5, "1M": 21, "3M": 63, "6M": 126}


@st.cache_data(ttl=900)
def load(tickers):
    df = yf.download(list(tickers), period="1y", auto_adjust=True, progress=False)["Close"]
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
        hi, lo, last = x.max(), x.min(), x.iloc[-1]
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

# ---- Heatmap (sector -> stocks)
st.caption("👆 Pehle sirf sectors dikhte hain. Kisi sector par tap karo to uske andar ke saare stocks khulenge. Stock par tap karke 52W high/low dekho. Wapas jane ke liye upar ke sector naam par tap karo.")
ids, labels, parents, vals, cols, texts, hovers = ["Sab sectors"], ["Sab sectors"], [""], [0], [0], [""], [""]
for sec, g in sdf.groupby("Sector", sort=False):
    sid = f"{sec} · {phase.get(sec, '')}"
    ids.append(sid); labels.append(sid); parents.append("Sab sectors"); vals.append(0)
    cols.append(g["Ret"].mean()); texts.append(f"{g['Ret'].mean():+.1f}%"); hovers.append(f"{sid}<br>Avg {g['Ret'].mean():.2f}%")
    for _, r in g.iterrows():
        ids.append(f"{sec}/{r.Stock}"); labels.append(r.Stock); parents.append(sid)
        vals.append(1 / len(g)); cols.append(r.Ret)
        texts.append(f"{r.Ret:+.1f}%<br>H {r['% from High']:.0f}% · L +{r['% above Low']:.0f}%")
        hovers.append(f"<b>{r.Stock}</b><br>{period}: {r.Ret:+.2f}%<br>Price {r.Price}"
                      f"<br>52W High {r['52W High']} ({r['% from High']}%)"
                      f"<br>52W Low {r['52W Low']} (+{r['% above Low']}%)")
lim = max(float(pd.Series(cols).abs().quantile(0.9)), 3)
fig = go.Figure(go.Treemap(
    ids=ids, labels=labels, parents=parents, values=vals, branchvalues="remainder", maxdepth=2,
    text=texts, hovertext=hovers, hoverinfo="text", texttemplate="<b>%{label}</b><br>%{text}",
    marker=dict(colors=cols, colorscale="RdYlGn", cmin=-lim, cmax=lim,
                colorbar=dict(title="%")),
    textfont_size=14))
fig.update_layout(height=640, margin=dict(t=10, l=0, r=0, b=0))
st.plotly_chart(fig, use_container_width=True)

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

# ---- Stock chart
st.subheader("📈 Stock chart")
opts = sorted({x for k, v in STOCKS.items() if pick == "Sab" or k == pick for x in v})
stk = st.selectbox("Stock chuno", opts)
rng = st.radio("Range", ["1M", "3M", "6M", "1Y"], index=2, horizontal=True)
days = {"1M": 21, "3M": 63, "6M": 126, "1Y": 252}[rng]


@st.cache_data(ttl=900)
def load_ohlc(tk):
    d = yf.download(tk, period="2y", auto_adjust=True, progress=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    return d.dropna()


d = load_ohlc(stk + ".NS")
if d.empty:
    st.warning("Is stock ka data nahi mila.")
else:
    d["MA50"] = d["Close"].rolling(50).mean()
    d["MA200"] = d["Close"].rolling(200).mean()
    hi, lo = d["Close"].tail(252).max(), d["Close"].tail(252).min()
    v = d.tail(days)
    cf = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.75, 0.25],
                       vertical_spacing=0.03)
    cf.add_trace(go.Candlestick(x=v.index, open=v["Open"], high=v["High"], low=v["Low"],
                                close=v["Close"], name=stk), row=1, col=1)
    cf.add_trace(go.Scatter(x=v.index, y=v["MA50"], name="50 DMA", line=dict(width=1.5)), row=1, col=1)
    cf.add_trace(go.Scatter(x=v.index, y=v["MA200"], name="200 DMA", line=dict(width=1.5)), row=1, col=1)
    cf.add_hline(y=hi, line_dash="dot", line_color="green", annotation_text=f"52W High {hi:.1f}", row=1, col=1)
    cf.add_hline(y=lo, line_dash="dot", line_color="red", annotation_text=f"52W Low {lo:.1f}", row=1, col=1)
    cf.add_trace(go.Bar(x=v.index, y=v["Volume"], name="Volume", marker_color="gray"), row=2, col=1)
    cf.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    cf.update_layout(height=560, xaxis_rangeslider_visible=False, margin=dict(t=10, l=0, r=0, b=0),
                     legend=dict(orientation="h", y=1.04))
    st.plotly_chart(cf, use_container_width=True)


st.caption("Data: yfinance (15 min cache). Sirf analysis ke liye, investment advice nahi.")
