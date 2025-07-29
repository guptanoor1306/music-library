# app.py
import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup

# Caching the result to prevent re-downloading every time
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

            # Basic rule-based categorization
            name_lower = name.lower()
            if any(word in name_lower for word in ["love", "heart", "romantic"]):
                mood = "Romantic"
            elif any(word in name_lower for word in ["trap", "beat", "energy", "fire", "hype"]):
                mood = "Energetic"
            elif any(word in name_lower for word in ["sad", "alone", "cry", "slow"]):
                mood = "Emotional"
            elif any(word in name_lower for word in ["fun", "happy", "party", "vibe"]):
                mood = "Upbeat"
            elif any(word in name_lower for word in ["suspense", "mystery", "dark"]):
                mood = "Suspense"
            else:
                mood = "Uncategorized"

            songs.append({
                "Rank": rank,
                "Song": name,
                "Artist": artist,
                "Reels Used": reels_used,
                "Mood": mood
            })
    return pd.DataFrame(songs)

# --- Streamlit UI ---
st.set_page_config(page_title="Trending IG Music by Mood", layout="wide")
st.title("🎶 Trending Instagram Music Library (Categorized by Mood)")

st.markdown("Top trending songs for Reels, categorized by vibe. Data sourced from [InBeat](https://www.inbeat.co/trending-instagram-songs/)")

# Fetch data
df = fetch_inbeat_trending_songs()

# Mood categories
categories = ['Upbeat', 'Energetic', 'Romantic', 'Emotional', 'Suspense', 'Uncategorized']
for mood in categories:
    st.subheader(f"🎧 {mood} Picks")
    filtered = df[df['Mood'] == mood].head(10)
    if not filtered.empty:
        st.dataframe(filtered[['Rank', 'Song', 'Artist', 'Reels Used']], use_container_width=True)
    else:
        st.markdown("_No songs found in this category right now._")

st.markdown("---")
st.caption("🔁 Updated live • Data from InBeat.co • Built with ❤️ using Streamlit")
