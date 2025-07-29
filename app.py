# app.py
import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup

@st.cache_data
def fetch_inbeat_trending_songs():
    url = "https://www.inbeat.co/trending-instagram-songs/"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')

    songs = []
    rows = soup.select("table tbody tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) >= 4:
            rank = cells[0].text.strip()
            name = cells[1].text.strip()
            artist = cells[2].text.strip()
            reels_used = cells[3].text.strip()
            songs.append({
                "Rank": rank,
                "Song": name,
                "Artist": artist,
                "Reels Used": reels_used
            })
    return pd.DataFrame(songs)

# --- UI ---
st.set_page_config(page_title="Trending IG Music Library", layout="wide")
st.title("🎶 Trending Instagram Music Library (from InBeat)")

st.markdown("See what's trending right now on Instagram Reels. Data sourced from [InBeat.co](https://www.inbeat.co/trending-instagram-songs/)")

with st.spinner("Fetching latest trending songs..."):
    df = fetch_inbeat_trending_songs()

# Filters and table
col1, col2 = st.columns([2, 1])
with col1:
    search = st.text_input("Search by song or artist")
with col2:
    limit = st.slider("Max Songs", 10, 50, 20)

if search:
    df = df[df['Song'].str.contains(search, case=False) | df['Artist'].str.contains(search, case=False)]

st.dataframe(df.head(limit), use_container_width=True)

st.markdown("\n---\n")
st.caption("🔁 Updated daily • Source: InBeat.co • Built with ❤️ using Streamlit")
