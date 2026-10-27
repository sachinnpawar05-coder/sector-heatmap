import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Sector Heatmap Scanner", layout="wide")
st.title("📊 NSE Sector Heatmap Scanner")

SECTORS = {
    "Bank": "^NSEBANK", "IT": "^CNXIT", "Pharma": "^CNXPHARMA", "Auto": "^CNXAUTO",
    "FMCG": "^CNXFMCG", "Metal": "^CNXMETAL", "Realty": "^CNXREALTY",
    "Energy": "^CNXENERGY", "PSU Bank": "^CNXPSUBANK", "Media": "^CNXMEDIA",
    "Infra": "^CNXINFRA", "Fin Services": "NIFTY_FIN_SERVICE.NS",
}
STOCKS = {
    "Bank": ["HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK"],
    "IT": ["TCS", "INFY", "HCLTECH", "WIPRO", "TECHM"],
    "Pharma": ["SUNPHARMA", "CIPLA", "DRREDDY", "DIVISLAB", "LUPIN"],
    "Auto": ["M&M", "MARUTI", "TATAMOTORS", "BAJAJ-AUTO", "EICHERMOT"],
    "FMCG": ["ITC", "HINDUNILVR", "NESTLEIND", "BRITANNIA", "TATACONSUM"],
    "Metal": ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "JINDALSTEL"],
    "Realty": ["DLF", "GODREJPROP", "LODHA", "OBEROIRLTY", "PRESTIGE"],
    "Energy": ["RELIANCE", "ONGC", "NTPC", "POWERGRID", "COALINDIA"],
    "PSU Bank": ["SBIN", "BANKBARODA", "PNB", "CANBK", "UNIONBANK"],
    "Media": ["ZEEL", "SUNTV", "PVRINOX", "NETWORK18", "TV18BRDCST"],
    "Infra": ["LT", "ADANIPORTS", "ULTRACEMCO", "GRASIM", "SIEMENS"],
    "Fin Services": ["BAJFINANCE", "BAJAJFINSV", "HDFCLIFE", "SBILIFE", "CHOLAFIN"],
}
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
lim = max(abs(df[mode]).max(), 1)
df["size"] = 1
fig = px.treemap(df, path=["Sector"], values="size", color=mode,
                 color_continuous_scale="RdYlGn", range_color=(-lim, lim),
                 color_continuous_midpoint=0, custom_data=["Return %", "Phase"])
fig.update_traces(texttemplate="<b>%{label}</b><br>%{customdata[0]:.2f}%<br>%{customdata[1]}",
                  textfont_size=18)
fig.update_layout(height=520, margin=dict(t=10, l=0, r=0, b=0))
st.plotly_chart(fig, use_container_width=True)

c1, c2 = st.columns(2)
c1.success("🟢 Abhi strong: " + ", ".join(df.nlargest(3, "Return %")["Sector"]))
nxt = df[df["Phase"].isin(["Improving", "Leading"])].nlargest(3, "RS Mom")["Sector"]
c2.info("🔭 Aage chal sakte hain (RS momentum): " + (", ".join(nxt) or "koi nahi"))

st.subheader("Ranking table")
st.dataframe(df.drop(columns="size").sort_values("Return %", ascending=False),
             use_container_width=True, hide_index=True)

st.subheader("Sector ke andar stocks")
sec = st.selectbox("Sector chuno", list(STOCKS))
tk = [s + ".NS" for s in STOCKS[sec]]
sp = load(tuple(tk))
srows = [{"Stock": c.replace(".NS", ""), "Return %": round(ret(sp[c], n), 2), "size": 1}
         for c in sp.columns if not sp[c].dropna().empty]
sdf = pd.DataFrame(srows).dropna()
if not sdf.empty:
    l2 = max(abs(sdf["Return %"]).max(), 1)
    f2 = px.treemap(sdf, path=["Stock"], values="size", color="Return %",
                    color_continuous_scale="RdYlGn", range_color=(-l2, l2),
                    color_continuous_midpoint=0, custom_data=["Return %"])
    f2.update_traces(texttemplate="<b>%{label}</b><br>%{customdata[0]:.2f}%", textfont_size=18)
    f2.update_layout(height=380, margin=dict(t=10, l=0, r=0, b=0))
    st.plotly_chart(f2, use_container_width=True)

st.caption("Data: yfinance (15 min cache). Sirf analysis ke liye, investment advice nahi.")
