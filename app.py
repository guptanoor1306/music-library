# app.py
import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup

@st.cache_data
def fetch_buffer_songs():
    url = "https://buffer.com/resources/trending-audio-instagram/?utm_source=chatgpt.com"
    res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(res.text, "html.parser")
    items = []
    for h3 in soup.select("h3"):
        title = h3.get_text(strip=True)
        desc = h3.find_next("p").get_text(strip=True) if h3.find_next("p") else ""
        # Try to find embed link if audio appears as link inside description
        link = None
        a = h3.find_next("a")
        if a and "instagram.com" in a.get("href", ""):
            link = a["href"]
        items.append({"Song": title, "Description": desc, "Embed": link})
    return pd.DataFrame(items)

@st.cache_data
def fetch_india_songs():
    url = "https://blog.bosswallah.com/trending-songs-on-instagram-reels-today/"
    res = requests.get(url, headers={"User-Agent":"Mozilla/5.0"})
    soup = BeautifulSoup(res.text, "html.parser")
    data = []
    ol = soup.find("ol")
    if not ol:
        return pd.DataFrame()
    for li in ol.find_all("li")[:10]:
        text = li.get_text(strip=True)
        parts = text.split("–")
        song = parts[0].strip().strip('"')
        artist = parts[1].split("–")[0].strip() if len(parts)>1 else ""
        uses = "approx " + ''.join(filter(str.isdigit, text)) + "+"
        data.append({"Song": song, "Artist": artist, "Reels Used": uses})
    return pd.DataFrame(data)

# UI
st.set_page_config(page_title="IG Trending Music & Previews", layout="wide")
st.title("🎧 Instagram Trending Audio (Global + India)")

st.header("🌍 Global via Buffer")
df_glob = fetch_buffer_songs()
if df_glob.empty:
    st.error("Failed to fetch global trends.")
else:
    for _, row in df_glob.head(10).iterrows():
        st.subheader(row['Song'])
        st.write(row['Description'])
        if row['Embed']:
            st.write(f"[Open on Instagram]({row['Embed']})")
        st.markdown("---")

st.header("🇮🇳 Popular in India")
df_in = fetch_india_songs()
if df_in.empty:
    st.error("Failed to fetch India trends.")
else:
    st.dataframe(df_in)

st.markdown("---")
st.caption("Sources: Buffer.com for global, BossWallah.com for India 🇮🇳")
