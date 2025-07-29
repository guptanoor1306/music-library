import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup

@st.cache_data
def fetch_buffer_top17():
    url = "https://buffer.com/resources/trending-audio-instagram/"
    res = requests.get(url, headers={"User-Agent":"Mozilla/5.0"})
    soup = BeautifulSoup(res.text, "html.parser")

    header = soup.find("h2", string=lambda t: t and "17 Trending Sounds" in t)
    if not header:
        return pd.DataFrame()
    songs = []
    ul = header.find_next_sibling("ul")
    if not ul:
        return pd.DataFrame()
    for li in ul.find_all("li", limit=17):
        text = li.get_text(separator=" ", strip=True)
        title = text.split("–")[0].split(". ",1)[-1]
        desc = li.find("p")
        desc_text = desc.get_text(strip=True) if desc else ""
        songs.append({"Song": title, "Details": desc_text})
    return pd.DataFrame(songs)

@st.cache_data
def fetch_india_top10():
    url = "https://blog.bosswallah.com/trending-songs-on-instagram-reels-today/"
    res = requests.get(url, headers={"User-Agent":"Mozilla/5.0"})
    soup = BeautifulSoup(res.text, "html.parser")
    h1 = soup.find("h1", string=lambda t: t and "Top 10 Trending Songs" in t)
    if not h1:
        return pd.DataFrame()
    songs = []
    for li in h1.find_next("ol").find_all("li", limit=10):
        raw = li.get_text(separator=" ", strip=True)
        parts = raw.split("–")
        song = parts[0].strip().strip('"')
        rest = parts[1] if len(parts)>1 else ""
        artist = rest.split("•")[0].strip() if "•" in rest else ""
        reels = ''.join([c for c in rest if c.isdigit() or c in "+,"]) or ""
        songs.append({"Song": song, "Artist": artist, "Reels Used": reels})
    return pd.DataFrame(songs)

st.set_page_config(page_title="Instagram Trending Audio", layout="wide")
st.title("🎧 Instagram Trending Audio (Global + India)")

df_glob = fetch_buffer_top17()
if df_glob.empty:
    st.error("⚠️ Couldn't fetch Buffer's trending list.")
else:
    st.header("🌍 Global (Top 17 via Buffer)")
    st.dataframe(df_glob, use_container_width=True)

df_ind = fetch_india_top10()
if df_ind.empty:
    st.error("⚠️ Couldn't fetch India trending list.")
else:
    st.header("🇮🇳 India (Top 10 via BossWallah)")
    st.dataframe(df_ind, use_container_width=True)

st.markdown("---")
st.caption("Sources: Buffer.com :contentReference[oaicite:11]{index=11}, BossWallah.com :contentReference[oaicite:12]{index=12} • Built with ❤️ using Streamlit")
