# app.py
import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup

# --- GLOBAL TRENDS (from Buffer.com) ---
@st.cache_data
def fetch_buffer_songs():
    url = "https://buffer.com/resources/trending-audio-instagram/"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")

    songs = []
    article = soup.find("article")
    if not article:
        return pd.DataFrame()

    headers = article.find_all("h3")
    for h in headers:
        song_title = h.get_text(strip=True)
        # Skip irrelevant section headings
        if any(x in song_title.lower() for x in ["create", "publish", "engage", "analyze", "start page"]):
            continue
        para = h.find_next_sibling("p")
        description = para.get_text(strip=True) if para else ""
        link = None
        a = h.find_next("a")
        if a and "instagram.com" in a.get("href", ""):
            link = a["href"]
        songs.append({
            "Song": song_title,
            "Why it's trending": description,
            "Preview Link": link
        })
    return pd.DataFrame(songs)

# --- INDIA-SPECIFIC TRENDS (from BossWallah) ---
@st.cache_data
def fetch_india_songs():
    url = "https://blog.bosswallah.com/trending-songs-on-instagram-reels-today/"
    headers = {"User-Agent":"Mozilla/5.0"}
    res = requests.get(url, headers=headers)
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
        uses = "approx " + ''.join(filter(str.isdigit, text)) + "+" if any(c.isdigit() for c in text) else ""
        data.append({"Song": song, "Artist": artist, "Reels Used": uses})
    return pd.DataFrame(data)

# --- STREAMLIT UI ---
st.set_page_config(page_title="Instagram Trending Music", layout="wide")
st.title("🎧 Instagram Trending Audio (Global + India)")

# GLOBAL SECTION
st.header("🌍 Global Trends (via Buffer)")
df_glob = fetch_buffer_songs()
if df_glob.empty:
    st.error("⚠️ Unable to fetch global trends from Buffer.")
else:
    for _, row in df_glob.iterrows():
    st.subheader(row['Song'])
    st.write(row["Why it's trending"])
    if row['Preview Link']:
        st.markdown(f"[🔗 Open on Instagram Audio Page]({row['Preview Link']})")
    st.markdown("---")

# INDIA SECTION
st.header("🇮🇳 Popular in India (via BossWallah)")
df_in = fetch_india_songs()
if df_in.empty:
    st.error("⚠️ Unable to fetch India-specific trends.")
else:
    st.dataframe(df_in, use_container_width=True)

# FOOTER
st.markdown("---")
st.caption("🎯 Sources: Buffer.com (global), BossWallah.com (India) • Built with ❤️ using Streamlit")
