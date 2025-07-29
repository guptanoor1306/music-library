# app.py
import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup

@st.cache_data
def fetch_buffer_trending_songs():
    url = "https://buffer.com/resources/trending-audio-instagram/?utm_source=chatgpt.com"
    res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(res.text, "html.parser")

    blocks = soup.select("h3")
    data = []
    for h3 in blocks:
        song_title = h3.get_text(strip=True)
        para = h3.find_next("p")
        description = para.get_text(strip=True) if para else ""
        
        # Basic mood tagging
        desc = description.lower()
        if any(word in desc for word in ["fun", "vibe", "dance", "party", "summer"]):
            mood = "Upbeat"
        elif any(word in desc for word in ["cry", "sad", "soft", "heart", "emotional"]):
            mood = "Emotional"
        elif any(word in desc for word in ["mystery", "dark", "slow build", "reveal"]):
            mood = "Suspense"
        elif any(word in desc for word in ["love", "romantic", "relationship"]):
            mood = "Romantic"
        elif any(word in desc for word in ["humor", "meme", "funny"]):
            mood = "Comedy"
        else:
            mood = "Uncategorized"

        data.append({
            "Song": song_title,
            "Mood": mood,
            "Why it's trending": description
        })

    return pd.DataFrame(data)

# --- UI ---
st.set_page_config(page_title="Trending IG Music by Mood", layout="wide")
st.title("🎵 Trending Instagram Music (via Buffer)")

st.markdown("Fetched from [Buffer's Trending Instagram Audio List](https://buffer.com/resources/trending-audio-instagram/)")

df = fetch_buffer_trending_songs()

if df.empty:
    st.error("⚠️ Unable to fetch trending songs from Buffer. Try again later.")
else:
    categories = ['Upbeat', 'Romantic', 'Emotional', 'Suspense', 'Comedy', 'Uncategorized']
    for mood in categories:
        st.subheader(f"🎧 {mood} Picks")
        filtered = df[df['Mood'] == mood].head(10)
        if not filtered.empty:
            st.dataframe(filtered, use_container_width=True)
        else:
            st.markdown("_No songs found in this category right now._")

st.markdown("---")
st.caption("🎯 Source: Buffer.com • Built with ❤️ using Streamlit")
