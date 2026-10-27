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

rows2 = []
for sec, syms in STOCKS.items():
    good = [s for s in syms if s + ".NS" in sp and not sp[s + ".NS"].dropna().empty]
    for s in good:
        r = ret(sp[s + ".NS"], n)
        if pd.isna(r):
            continue
        r = r - nret if mode == "vs Nifty %" else r
        rows2.append({"Sector": f"{sec} · {phase.get(sec, '')}", "Stock": s,
                      "Ret": round(r, 2), "w": 1 / len(good)})
tdf = pd.DataFrame(rows2)

st.caption("👆 Kisi bhi sector ke box par tap karo, uske andar ke saare stocks khul jayenge. Wapas jane ke liye upar ka naam ya box ke bahar tap karo.")
lim = max(abs(tdf["Ret"]).max(), 1)
fig = px.treemap(tdf, path=["Sector", "Stock"], values="w", color="Ret",
                 color_continuous_scale="RdYlGn", range_color=(-lim, lim),
                 color_continuous_midpoint=0)
fig.update_traces(texttemplate="<b>%{label}</b><br>%{color:.2f}%", textfont_size=16,
                  hovertemplate="%{label}<br>%{color:.2f}%<extra></extra>")
fig.update_layout(height=620, margin=dict(t=30, l=0, r=0, b=0), coloraxis_colorbar_title="%")
st.plotly_chart(fig, use_container_width=True)

c1, c2 = st.columns(2)
c1.success("🟢 Abhi strong: " + ", ".join(df.nlargest(3, "Return %")["Sector"]))
nxt = df[df["Phase"].isin(["Improving", "Leading"])].nlargest(3, "RS Mom")["Sector"]
c2.info("🔭 Aage chal sakte hain (RS momentum): " + (", ".join(nxt) or "koi nahi"))

st.subheader("Sector ranking")
st.dataframe(df.drop(columns="size", errors="ignore").sort_values("Return %", ascending=False),
             use_container_width=True, hide_index=True)

st.subheader("Saare stocks (table)")
sec = st.selectbox("Sector chuno", list(STOCKS))
st.dataframe(tdf[tdf["Sector"].str.startswith(sec + " ·")][["Stock", "Ret"]]
             .rename(columns={"Ret": mode}).sort_values(mode, ascending=False),
             use_container_width=True, hide_index=True)

st.caption("Data: yfinance (15 min cache). Sirf analysis ke liye, investment advice nahi.")
