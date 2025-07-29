import streamlit as st
import requests
import json
from typing import List, Dict, Any, Tuple
import pandas as pd
from datetime import datetime
import re
from urllib.parse import quote_plus, urlencode
import time
import hashlib
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import logging
from collections import defaultdict, Counter
import difflib

# Page configuration
st.set_page_config(
    page_title="B-Roll Library",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state for persistent data
if 'search_results' not in st.session_state:
    st.session_state.search_results = []
if 'current_query' not in st.session_state:
    st.session_state.current_query = ""
if 'youtube_embeds' not in st.session_state:
    st.session_state.youtube_embeds = {}
if 'show_more_states' not in st.session_state:
    st.session_state.show_more_states = {}
if 'active_tab' not in st.session_state:
    st.session_state.active_tab = "all"

# Custom CSS for better styling
st.markdown("""
<style>
.main-header {
    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    padding: 1rem;
    border-radius: 10px;
    margin-bottom: 2rem;
}
.source-tag {
    display: inline-block;
    padding: 0.25rem 0.5rem;
    border-radius: 12px;
    font-size: 0.9rem;
    font-weight: bold;
    margin-right: 0.5rem;
}
.my-sources { background-color: #e3f2fd; color: #1976d2; }
.youtube { background-color: #ffebee; color: #d32f2f; }
.web { background-color: #e8f5e8; color: #388e3c; }
.match-score {
    display: inline-block;
    padding: 0.2rem 0.4rem;
    border-radius: 8px;
    font-size: 0.8rem;
    font-weight: bold;
    margin-left: 0.5rem;
}
.direct-match { background-color: #4caf50; color: white; }
.semantic-match { background-color: #ff9800; color: white; }
.keyword-match { background-color: #2196f3; color: white; }
</style>
""", unsafe_allow_html=True)

class SemanticSearchEngine:
    """Enhanced search engine with semantic matching capabilities"""
    
    def __init__(self):
        # Semantic keyword mappings for better search matching
        self.semantic_mappings = {
            'business': ['corporate', 'office', 'meeting', 'professional', 'work', 'conference', 'presentation', 'team', 'finance', 'startup'],
            'technology': ['tech', 'digital', 'computer', 'software', 'AI', 'coding', 'programming', 'innovation', 'gadgets', 'electronics'],
            'nature': ['outdoor', 'forest', 'trees', 'mountains', 'water', 'landscape', 'wildlife', 'green', 'natural', 'environment'],
            'city': ['urban', 'buildings', 'skyline', 'street', 'traffic', 'architecture', 'downtown', 'metropolitan', 'cityscape'],
            'people': ['human', 'person', 'crowd', 'family', 'friends', 'social', 'community', 'lifestyle', 'portrait'],
            'food': ['cooking', 'restaurant', 'kitchen', 'dining', 'meal', 'culinary', 'recipe', 'chef', 'eating'],
            'travel': ['vacation', 'tourism', 'journey', 'adventure', 'destination', 'explore', 'trip', 'wanderlust'],
            'sports': ['fitness', 'exercise', 'athletic', 'training', 'competition', 'gym', 'workout', 'activity'],
            'music': ['sound', 'audio', 'concert', 'performance', 'instruments', 'rhythm', 'melody', 'dance'],
            'art': ['creative', 'design', 'painting', 'drawing', 'artistic', 'gallery', 'visual', 'aesthetic']
        }
        
        # Create reverse mapping for faster lookup
        self.reverse_mappings = {}
        for main_term, related_terms in self.semantic_mappings.items():
            for term in related_terms:
                if term not in self.reverse_mappings:
                    self.reverse_mappings[term] = []
                self.reverse_mappings[term].append(main_term)
    
    def extract_keywords(self, query: str) -> List[str]:
        """Extract and clean keywords from search query"""
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        
        # Clean and split query
        keywords = re.findall(r'\b\w+\b', query.lower())
        keywords = [word for word in keywords if word not in stop_words and len(word) > 2]
        
        return keywords
    
    def expand_keywords(self, keywords: List[str]) -> Dict[str, List[str]]:
        """Expand keywords with semantic variations"""
        expanded = {
            'original': keywords,
            'semantic': [],
            'related': []
        }
        
        for keyword in keywords:
            # Direct semantic mapping
            if keyword in self.semantic_mappings:
                expanded['semantic'].extend(self.semantic_mappings[keyword])
            
            # Reverse mapping (if keyword is a related term)
            if keyword in self.reverse_mappings:
                expanded['related'].extend(self.reverse_mappings[keyword])
                # Also add related terms from main categories
                for main_term in self.reverse_mappings[keyword]:
                    if main_term in self.semantic_mappings:
                        expanded['semantic'].extend(self.semantic_mappings[main_term])
        
        # Remove duplicates
        expanded['semantic'] = list(set(expanded['semantic']))
        expanded['related'] = list(set(expanded['related']))
        
        return expanded
    
    def calculate_match_score(self, result: Dict, query_keywords: Dict[str, List[str]], original_query: str) -> Tuple[float, str]:
        """Calculate relevance score for a search result"""
        title = result.get('title', '').lower()
        description = result.get('description', '').lower()
        content = f"{title} {description}"
        
        scores = {
            'direct': 0,
            'keyword': 0,
            'semantic': 0,
            'fuzzy': 0
        }
        
        # Direct query match (highest priority)
        if original_query.lower() in content:
            scores['direct'] = 100
        
        # Original keyword matches
        for keyword in query_keywords['original']:
            if keyword in content:
                scores['keyword'] += 20
        
        # Semantic keyword matches
        for keyword in query_keywords['semantic']:
            if keyword in content:
                scores['semantic'] += 10
        
        # Related keyword matches
        for keyword in query_keywords['related']:
            if keyword in content:
                scores['semantic'] += 15
        
        # Fuzzy matching for similar words
        all_words = re.findall(r'\b\w+\b', content)
        for query_word in query_keywords['original']:
            for word in all_words:
                similarity = difflib.SequenceMatcher(None, query_word, word).ratio()
                if similarity > 0.8 and similarity < 1.0:  # Similar but not exact
                    scores['fuzzy'] += similarity * 5
        
        # Calculate total score
        total_score = scores['direct'] + scores['keyword'] + scores['semantic'] + scores['fuzzy']
        
        # Determine match type
        if scores['direct'] > 0:
            match_type = 'direct'
        elif scores['keyword'] > scores['semantic']:
            match_type = 'keyword'
        else:
            match_type = 'semantic'
        
        return total_score, match_type

class BRollLibrary:
    def __init__(self):
        # Initialize semantic search engine
        self.semantic_engine = SemanticSearchEngine()
        
        # YouTube API Configuration
        self.youtube_api_key = st.secrets.get("YOUTUBE_API_KEY", "")
        self.youtube_service = None
        if self.youtube_api_key:
            try:
                self.youtube_service = build('youtube', 'v3', developerKey=self.youtube_api_key)
            except Exception as e:
                st.error(f"Failed to initialize YouTube API: {e}")
        
        # Defined sources configuration
        self.defined_sources = {
            'pexels': {
                'name': 'Pexels',
                'url': 'https://www.pexels.com/',
                'description': 'Free stock videos and photos',
                'api_available': True,
                'api_key': st.secrets.get("PEXELS_API_KEY", "")
            },
            'playphrase': {
                'name': 'PlayPhrase.me',
                'url': 'https://www.playphrase.me/#/search?language=en',
                'description': 'Movie and TV show clips with specific phrases',
                'api_available': False
            },
            'clip_cafe': {
                'name': 'Clip.cafe',
                'url': 'https://clip.cafe/',
                'description': 'Movie and TV show clips database',
                'api_available': False
            },
            'yarn': {
                'name': 'Yarn.co',
                'url': 'https://yarn.co/',
                'description': 'Movie and TV show quotes with video clips',
                'api_available': False
            }
        }
    
    def enhance_query_for_search(self, original_query: str) -> str:
        """Enhance the search query with semantic keywords"""
        keywords = self.semantic_engine.extract_keywords(original_query)
        expanded_keywords = self.semantic_engine.expand_keywords(keywords)
        
        # Create enhanced query with top semantic matches
        enhanced_terms = keywords.copy()
        enhanced_terms.extend(expanded_keywords['semantic'][:3])  # Add top 3 semantic matches
        enhanced_terms.extend(expanded_keywords['related'][:2])   # Add top 2 related terms
        
        return ' '.join(enhanced_terms)
    
    def sort_results_by_relevance(self, results: List[Dict], original_query: str) -> List[Dict]:
        """Sort results by relevance using semantic matching"""
        if not results:
            return results
        
        keywords = self.semantic_engine.extract_keywords(original_query)
        expanded_keywords = self.semantic_engine.expand_keywords(keywords)
        
        # Calculate scores for all results
        scored_results = []
        for result in results:
            score, match_type = self.semantic_engine.calculate_match_score(result, expanded_keywords, original_query)
            result['_relevance_score'] = score
            result['_match_type'] = match_type
            scored_results.append(result)
        
        # Sort by score (descending) and then by match type priority
        match_type_priority = {'direct': 0, 'keyword': 1, 'semantic': 2}
        scored_results.sort(key=lambda x: (-x['_relevance_score'], match_type_priority.get(x['_match_type'], 3)))
        
        return scored_results
    
    def search_my_sources(self, query: str) -> List[Dict]:
        """Search through all 4 defined sources with enhanced query"""
        enhanced_query = self.enhance_query_for_search(query)
        all_results = []
        
        # Search Pexels
        if self.defined_sources['pexels']['api_key']:
            pexels_results = self.search_pexels(enhanced_query)
            all_results.extend(pexels_results)
        else:
            all_results.extend(self.search_pexels_mock(enhanced_query))
        
        # Search other sources with enhanced query
        playphrase_results = self.search_playphrase_mock(enhanced_query)
        all_results.extend(playphrase_results)
        
        clipcafe_results = self.search_clipcafe_mock(enhanced_query)
        all_results.extend(clipcafe_results)
        
        yarn_results = self.search_yarn_mock(enhanced_query)
        all_results.extend(yarn_results)
        
        # Sort by relevance before returning
        return self.sort_results_by_relevance(all_results, query)
    
    def search_pexels(self, query: str) -> List[Dict]:
        """Search Pexels using their API"""
        if not self.defined_sources['pexels']['api_key']:
            return self.search_pexels_mock(query)
        
        try:
            headers = {'Authorization': self.defined_sources['pexels']['api_key']}
            url = f"https://api.pexels.com/videos/search"
            params = {'query': query, 'per_page': 5, 'orientation': 'all'}
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                results = []
                
                for video in data.get('videos', [])[:5]:
                    result = {
                        'title': f"Pexels: {query.title()} Video",
                        'description': f"High-quality {query} footage from Pexels",
                        'url': video.get('url', ''),
                        'thumbnail': video.get('image', ''),
                        'duration': f"{video.get('duration', 0)}s",
                        'resolution': f"{video.get('width', 0)}x{video.get('height', 0)}",
                        'source_type': 'my_sources',
                        'source_name': 'Pexels',
                        'license': 'Free for commercial use'
                    }
                    results.append(result)
                
                return results
            else:
                return self.search_pexels_mock(query)
            
        except Exception as e:
            return self.search_pexels_mock(query)
    
    # Mock search methods remain the same but with more varied content
    def search_pexels_mock(self, query: str) -> List[Dict]:
        """Mock Pexels search results with more variety"""
        video_types = ["4K Professional", "HD Cinematic", "Ultra HD", "Professional Stock", "Premium Quality"]
        return [{
            'title': f"Pexels: {query.title()} {video_types[i % len(video_types)]}",
            'description': f"Professional {query} stock footage from Pexels - {video_types[i % len(video_types)].lower()} quality",
            'url': f"https://www.pexels.com/search/videos/{query.replace(' ', '%20')}/",
            'thumbnail': "https://images.pexels.com/videos/3045163/free-video-3045163.jpg",
            'duration': f"0:{25 + (i * 10)}",
            'resolution': "1920x1080" if i % 2 == 0 else "3840x2160",
            'source_type': 'my_sources',
            'source_name': 'Pexels',
            'license': 'Free for commercial use'
        } for i in range(2)]
    
    def search_playphrase_mock(self, query: str) -> List[Dict]:
        """Mock PlayPhrase.me search results"""
        return [{
            'title': f'Movie Clip: "{query}"',
            'description': f'Movie and TV clips containing phrases related to "{query}" - perfect for social media content',
            'url': f"https://www.playphrase.me/#/search?q={quote_plus(query)}",
            'thumbnail': '',
            'duration': "0:05",
            'resolution': "Various",
            'source_type': 'my_sources',
            'source_name': 'PlayPhrase.me',
            'license': 'Fair use clips'
        }]
    
    def search_clipcafe_mock(self, query: str) -> List[Dict]:
        """Mock Clip.cafe search results"""
        return [{
            'title': f'TV/Movie Scene: {query.title()}',
            'description': f'Curated movie and TV show clips related to {query} - trending content for creators',
            'url': f"https://clip.cafe/search?q={quote_plus(query)}",
            'thumbnail': '',
            'duration': "0:08",
            'resolution': "HD",
            'source_type': 'my_sources',
            'source_name': 'Clip.cafe',
            'license': 'Educational/Fair use'
        }]
    
    def search_yarn_mock(self, query: str) -> List[Dict]:
        """Mock Yarn.co search results"""
        return [{
            'title': f'Yarn: "{query}" Quote Collection',
            'description': f'Movie and TV quotes containing "{query}" perfect for viral social media content and memes',
            'url': f"https://yarn.co/yarn-find?text={quote_plus(query)}",
            'thumbnail': '',
            'duration': "0:06",
            'resolution': "Variable",
            'source_type': 'my_sources',
            'source_name': 'Yarn.co',
            'license': 'Fair use clips'
        }]
    
    def search_youtube(self, query: str, max_results: int = 20) -> List[Dict]:
        """Search YouTube using enhanced query"""
        enhanced_query = self.enhance_query_for_search(query)
        
        if not self.youtube_service:
            return self.sort_results_by_relevance(self.search_youtube_mock(enhanced_query, max_results), query)
        
        try:
            search_response = self.youtube_service.search().list(
                q=enhanced_query + " b-roll footage stock video",
                part='id,snippet',
                maxResults=max_results,
                type='video',
                videoDefinition='high',
                videoLicense='any',
                order='relevance'
            ).execute()
            
            results = []
            
            for search_result in search_response.get('items', []):
                video_id = search_result['id']['videoId']
                snippet = search_result['snippet']
                
                result = {
                    'title': snippet['title'],
                    'description': snippet['description'][:200] + '...' if len(snippet['description']) > 200 else snippet['description'],
                    'url': f"https://www.youtube.com/watch?v={video_id}",
                    'thumbnail': snippet['thumbnails']['high']['url'],
                    'duration': "Variable",
                    'channel': snippet['channelTitle'],
                    'published': snippet['publishedAt'][:10],
                    'source_type': 'youtube',
                    'video_id': video_id
                }
                results.append(result)
            
            return self.sort_results_by_relevance(results, query)
            
        except Exception as e:
            return self.sort_results_by_relevance(self.search_youtube_mock(enhanced_query, max_results), query)
    
    def search_youtube_mock(self, query: str, max_results: int = 20) -> List[Dict]:
        """Enhanced mock YouTube search results"""
        video_types = [
            ("Professional B-Roll Footage - 4K Stock Video", "High-quality footage perfect for commercial use", "Stock Footage Pro"),
            ("Free Video Background - No Copyright", "No copyright background video for content creators", "Creative Commons Videos"),
            ("Cinematic B-Roll Collection", "Beautiful cinematic footage for your projects", "Filmmaker Central"),
            ("Stock Video Compilation", "Multiple high-quality stock video clips", "Video Library"),
            ("4K Nature Footage", "Stunning nature scenes in ultra high definition", "Nature Videos HD"),
            ("Urban City B-Roll", "Modern city scenes and architecture", "Urban Footage"),
            ("Business Meeting Stock Video", "Professional business scenarios", "Corporate Videos"),
            ("Technology B-Roll Pack", "Modern tech and digital content", "Tech Stock"),
            ("Lifestyle Stock Footage", "Everyday life and lifestyle content", "Lifestyle Media"),
            ("Creative B-Roll Bundle", "Artistic and creative video content", "Creative Studio")
        ]
        
        mock_results = []
        for i in range(min(max_results, len(video_types))):
            title_template, desc_template, channel = video_types[i % len(video_types)]
            
            result = {
                "title": f"{query.title()} {title_template}",
                "description": f"{query.title()} {desc_template.lower()}",
                "url": f"https://youtube.com/results?search_query={quote_plus(query + ' b-roll footage')}",
                "thumbnail": "",
                "duration": f"{1 + (i % 4)}:{30 + (i * 15) % 60:02d}",
                "channel": channel,
                "published": f"2024-{1 + (i % 12):02d}-{1 + (i % 28):02d}",
                "source_type": "youtube",
                "video_id": f"dQw4w9WgXc{i:02d}"
            }
            mock_results.append(result)
        
        return mock_results
    
    def search_web_sources(self, query: str, max_results: int = 20) -> List[Dict]:
        """Search web using enhanced query"""
        enhanced_query = self.enhance_query_for_search(query)
        
        # Try Google CSE first if available
        cse_results = self.search_google_cse(enhanced_query, max_results)
        if cse_results:
            return self.sort_results_by_relevance(cse_results, query)
        
        # Fallback to curated sources
        results = self.search_curated_web_sources(enhanced_query, max_results)
        return self.sort_results_by_relevance(results, query)
    
    def search_google_cse(self, query: str, max_results: int = 20) -> List[Dict]:
        """Search using Google Custom Search Engine for video content"""
        google_api_key = st.secrets.get("GOOGLE_API_KEY", "")
        cse_id = st.secrets.get("GOOGLE_CSE_ID", "")
        
        if not google_api_key or not cse_id:
            return []
        
        try:
            search_url = "https://www.googleapis.com/customsearch/v1"
            params = {
                'key': google_api_key,
                'cx': cse_id,
                'q': f"{query} b-roll stock video footage free",
                'num': min(max_results, 10),
                'searchType': 'image',
                'fileType': 'mp4,mov,avi',
                'rights': 'cc_publicdomain,cc_attribute,cc_sharealike,cc_noncommercial,cc_nonderived'
            }
            
            response = requests.get(search_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                results = []
                
                for i, item in enumerate(data.get('items', [])):
                    result = {
                        'title': f"{query.title()} - {item.get('title', 'Video Content')}",
                        'description': item.get('snippet', f"High-quality {query} video content from web search"),
                        'url': item.get('link', ''),
                        'thumbnail': item.get('image', {}).get('thumbnailLink', ''),
                        'duration': f"0:{30 + (i * 10)}",
                        'resolution': "HD",
                        'license': "Various Creative Commons",
                        'source': item.get('displayLink', 'Web Source'),
                        'source_type': 'web'
                    }
                    results.append(result)
                
                return results
            
        except Exception as e:
            st.warning(f"Google CSE search failed: {e}")
        
        return []
    
    def search_curated_web_sources(self, query: str, max_results: int = 20) -> List[Dict]:
        """Enhanced curated web sources search"""
        web_sources = [
            {
                "name": "Pexels Videos",
                "base_url": "https://www.pexels.com/search/videos/",
                "description": "Free stock videos from Pexels",
                "license": "Free for commercial use",
                "quality": "4K"
            },
            {
                "name": "Coverr",
                "base_url": "https://coverr.co/search?q=",
                "description": "Beautiful stock video footage",
                "license": "Free for commercial use",
                "quality": "HD"
            },
            {
                "name": "Mixkit",
                "base_url": "https://mixkit.co/free-stock-video/",
                "description": "Free video clips and music",
                "license": "Mixkit License",
                "quality": "4K"
            },
            {
                "name": "Pixabay Videos", 
                "base_url": "https://pixabay.com/videos/search/",
                "description": "Royalty-free video content",
                "license": "Pixabay License",
                "quality": "4K"
            },
            {
                "name": "Videvo",
                "base_url": "https://www.videvo.net/search/",
                "description": "Free stock video footage",
                "license": "Various licenses",
                "quality": "HD"
            }
        ]
        
        results = []
        
        for i, source in enumerate(web_sources):
            if len(results) >= max_results:
                break
            
            # Build search URL
            if source["name"] == "Coverr":
                search_url = f"{source['base_url']}{query.replace(' ', '+')}"
            elif source["name"] == "Pixabay Videos":
                search_url = f"{source['base_url']}{query.replace(' ', '%20')}/"
            else:
                search_url = f"{source['base_url']}{query.replace(' ', '%20')}"
            
            result = {
                'title': f"{query.title()} - {source['name']}",
                'description': f"High-quality {query} video content from {source['name']}. {source['description']}",
                'url': search_url,
                'thumbnail': '',
                'duration': f"0:{15 + (i * 5) % 60}",
                'resolution': source['quality'],
                'license': source['license'],
                'source': source['name'],
                'source_type': 'web'
            }
            results.append(result)
        
        return results

def display_search_result(result: Dict, source_type: str):
    """Display a single search result with relevance indicators"""
    with st.container():
        col1, col2 = st.columns([4, 7])
        
        unique_key = f"{result.get('_display_id', 'unknown')}_{result.get('source_name', 'source')}"
        video_id = result.get('video_id', '')
        embed_key = f"embed_{unique_key}"
        
        with col1:
            # YouTube embed handling
            if (result.get('source_type') == 'youtube' and 
                video_id and 
                st.session_state.youtube_embeds.get(embed_key, False)):
                
                youtube_html = f"""
                <iframe width="350" height="220" 
                        src="https://www.youtube.com/embed/{video_id}?autoplay=1&rel=0&modestbranding=1" 
                        title="YouTube video player" 
                        frameborder="0" 
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" 
                        allowfullscreen>
                </iframe>
                """
                st.markdown(youtube_html, unsafe_allow_html=True)
            else:
                # Thumbnail or placeholder
                thumbnail_displayed = False
                
                if 'thumbnail' in result and result['thumbnail']:
                    try:
                        st.image(result['thumbnail'], width=350)
                        thumbnail_displayed = True
                    except:
                        pass
                
                if not thumbnail_displayed:
                    source_name = result.get('source_name', 'Unknown')
                    # Different colored placeholders for different sources
                    placeholder_colors = {
                        'Pexels': '#05A081',
                        'PlayPhrase.me': '#FF6B6B',
                        'Clip.cafe': '#A8E6CF',
                        'Yarn.co': '#FFD93D',
                        'YouTube': '#FF0000',
                        'default': '#667eea'
                    }
                    color = placeholder_colors.get(source_name, placeholder_colors['default'])
                    
                    st.markdown(f"""
                    <div style="width: 350px; height: 220px; background: linear-gradient(45deg, {color}, {color}aa); 
                                display: flex; align-items: center; justify-content: center; border-radius: 15px; color: white; font-weight: bold; text-align: center; font-size: 24px;">
                        🎬<br>{source_name}<br>Video
                    </div>
                    """, unsafe_allow_html=True)
        
        with col2:
            # Source tag and relevance indicator
            col_tag, col_score = st.columns([3, 1])
            
            with col_tag:
                if source_type == 'my_sources':
                    st.markdown('<span class="source-tag my-sources">My Sources</span>', unsafe_allow_html=True)
                elif source_type == 'youtube':
                    st.markdown('<span class="source-tag youtube">YouTube</span>', unsafe_allow_html=True)
                else:
                    st.markdown('<span class="source-tag web">Web</span>', unsafe_allow_html=True)
            
            with col_score:
                # Display match type indicator
                match_type = result.get('_match_type', 'semantic')
                relevance_score = result.get('_relevance_score', 0)
                
                if match_type == 'direct':
                    st.markdown('<span class="match-score direct-match">🎯 Direct</span>', unsafe_allow_html=True)
                elif match_type == 'keyword':
                    st.markdown('<span class="match-score keyword-match">🔑 Keyword</span>', unsafe_allow_html=True)
                else:
                    st.markdown('<span class="match-score semantic-match">🧠 Semantic</span>', unsafe_allow_html=True)
            
            # Title with relevance score
            score_display = f" ({relevance_score:.0f})" if relevance_score > 0 else ""
            st.markdown(f"## {result['title']}{score_display}")
            st.markdown(f"**{result['description']}**")
            
            # Additional info in metrics
            info_cols = st.columns(4)
            with info_cols[0]:
                if 'duration' in result:
                    st.metric("⏱️ Duration", result['duration'])
            with info_cols[1]:
                if 'resolution' in result:
                    st.metric("📺 Resolution", result['resolution'])
                elif 'channel' in result:
                    st.metric("📺 Channel", result['channel'])
            with info_cols[2]:
                if 'license' in result:
                    st.metric("📄 License", result['license'])
            with info_cols[3]:
                if 'source' in result:
                    st.metric("🔗 Source", result['source'])
                elif 'source_name' in result:
                    st.metric("🔗 Source", result['source_name'])
            
            st.markdown("---")
            
            # Special handling for YouTube - embed player
            if result.get('source_type') == 'youtube' and result.get('video_id'):
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    is_playing = st.session_state.youtube_embeds.get(embed_key, False)
                    button_text = "❌ Stop" if is_playing else "▶️ Play Here"
                    
                    if st.button(button_text, key=f"play_embed_{unique_key}", use_container_width=True):
                        st.session_state.youtube_embeds[embed_key] = not st.session_state.youtube_embeds.get(embed_key, False)
                        st.rerun()
                
                with col_btn2:
                    st.link_button("🔗 Open YouTube", result['url'], use_container_width=True)
            else:
                st.link_button("🔗 OPEN VIDEO", result['url'], use_container_width=True, type="primary")
        
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.divider()

def display_search_insights(query: str, results: List[Dict]):
    """Display search insights and keyword analysis"""
    if not results:
        return
    
    # Initialize semantic engine for analysis
    semantic_engine = SemanticSearchEngine()
    keywords = semantic_engine.extract_keywords(query)
    expanded_keywords = semantic_engine.expand_keywords(keywords)
    
    with st.expander("🔍 Search Insights & Keywords Analysis", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Original Keywords")
            if keywords:
                keyword_str = ", ".join([f"`{kw}`" for kw in keywords])
                st.markdown(keyword_str)
            else:
                st.write("No specific keywords detected")
            
            st.subheader("Match Distribution")
            match_counts = Counter([r.get('_match_type', 'unknown') for r in results])
            for match_type, count in match_counts.items():
                emoji = {"direct": "🎯", "keyword": "🔑", "semantic": "🧠"}.get(match_type, "❓")
                st.write(f"{emoji} {match_type.title()}: {count} results")
        
        with col2:
            st.subheader("Semantic Expansions")
            if expanded_keywords['semantic']:
                semantic_str = ", ".join([f"`{kw}`" for kw in expanded_keywords['semantic'][:10]])
                st.markdown(f"**Related terms:** {semantic_str}")
            
            if expanded_keywords['related']:
                related_str = ", ".join([f"`{kw}`" for kw in expanded_keywords['related'][:5]])
                st.markdown(f"**Category matches:** {related_str}")
            
            st.subheader("Search Quality")
            avg_score = sum([r.get('_relevance_score', 0) for r in results]) / len(results) if results else 0
            st.metric("Average Relevance Score", f"{avg_score:.1f}")

def perform_search(broll_lib, search_query, search_my_sources, search_youtube, search_web):
    """Perform search and store results in session state"""
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    all_results = []
    
    # Search My Sources
    if search_my_sources:
        status_text.text("🔍 Using semantic search on your defined sources...")
        progress_bar.progress(20)
        my_results = broll_lib.search_my_sources(search_query)
        all_results.extend(my_results)
        time.sleep(0.5)
    
    # Search YouTube
    if search_youtube:
        status_text.text("🔍 Searching YouTube with enhanced keywords...")
        progress_bar.progress(50 if search_my_sources else 20)
        youtube_results = broll_lib.search_youtube(search_query)
        all_results.extend(youtube_results)
        time.sleep(0.5)
    
    # Search Web
    if search_web:
        status_text.text("🔍 Searching web libraries with semantic matching...")
        progress_bar.progress(80 if (search_my_sources or search_youtube) else 20)
        web_results = broll_lib.search_web_sources(search_query)
        if web_results:
            all_results.extend(web_results)
        time.sleep(0.5)
    
    # Final sort by relevance across all sources
    status_text.text("🧠 Applying semantic ranking and sorting...")
    progress_bar.progress(95)
    all_results = broll_lib.sort_results_by_relevance(all_results, search_query)
    
    progress_bar.progress(100)
    status_text.text("✅ Search completed with semantic analysis!")
    time.sleep(0.5)
    progress_bar.empty()
    status_text.empty()
    
    # Store results in session state
    st.session_state.search_results = all_results
    st.session_state.current_query = search_query
    
    # Reset show more states for new search
    st.session_state.show_more_states = {}
    st.session_state.youtube_embeds = {}

def display_results_section_smooth(results, section_name, initial_count=5, show_all=False):
    """Display results with smooth expand/collapse without page refresh"""
    if not results:
        return
    
    if show_all:
        for j in range(len(results)):
            result = results[j]
            result['_display_id'] = f"{section_name}_{j}"
            display_search_result(result, result['source_type'])
    else:
        show_more_key = f"show_more_{section_name}"
        
        show_more = st.session_state.show_more_states.get(show_more_key, False)
        results_to_show = len(results) if show_more else min(initial_count, len(results))
        
        # Display results up to the current limit
        for j in range(results_to_show):
            result = results[j]
            result['_display_id'] = f"{section_name}_{j}"
            display_search_result(result, result['source_type'])
        
        # Show button only if there are more results to show
        if len(results) > initial_count:
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                if not show_more:
                    if st.button("📄 Show More Results", key=f"btn_more_{section_name}", use_container_width=True):
                        st.session_state.show_more_states[show_more_key] = True
                        st.rerun()
                else:
                    if st.button("📄 Show Less", key=f"btn_less_{section_name}", use_container_width=True):
                        st.session_state.show_more_states[show_more_key] = False
                        st.rerun()

def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h1 style="color: white; margin: 0;">🎬 B-Roll Library</h1>
        <p style="color: white; margin: 0; opacity: 0.9;">Find the perfect B-roll footage with AI-powered semantic search</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize the library
    broll_lib = BRollLibrary()
    
    # Sidebar
    with st.sidebar:
        st.header("🔧 Search Settings")
        
        # Search sources selection
        st.subheader("Select Sources")
        search_my_sources = st.checkbox("My Sources (4 Defined)", value=True)
        search_youtube = st.checkbox("YouTube", value=True)
        search_web = st.checkbox("Web Libraries", value=True)
        
        st.divider()
        
        # Semantic search info
        st.subheader("🧠 Semantic Search")
        st.info("""
        **Enhanced Features:**
        - Keyword expansion
        - Semantic matching
        - Relevance scoring
        - Smart result ranking
        """)
        
        # Statistics
        st.subheader("📊 Library Stats")
        st.metric("Defined Sources", len(broll_lib.defined_sources))
        st.metric("Total Searches", st.session_state.get('total_searches', 0))
        
        # API Status
        st.subheader("🔌 API Status")
        if broll_lib.youtube_service:
            st.success("✅ YouTube API Connected")
        else:
            st.error("❌ YouTube API Not Connected")
        
        if broll_lib.defined_sources['pexels']['api_key']:
            st.success("✅ Pexels API Connected")
        else:
            st.warning("⚠️ Pexels API Not Connected")
        
        google_api_key = st.secrets.get("GOOGLE_API_KEY", "")
        cse_id = st.secrets.get("GOOGLE_CSE_ID", "")
        if google_api_key and cse_id:
            st.success("✅ Google CSE Connected")
        else:
            st.warning("⚠️ Google CSE Not Connected")
        
        st.success("✅ Semantic Engine Ready")
        st.caption("AI-powered search with keyword expansion")
    
    # Main search interface
    search_col1, search_col2 = st.columns([5, 1])
    
    with search_col1:
        search_query = st.text_input(
            "🔍 Search for B-roll footage (AI-enhanced)",
            placeholder="e.g., business meeting, city skyline, technology, nature...",
            key="search_input",
            help="The AI will automatically expand your search with related terms for better results"
        )
    
    with search_col2:
        st.markdown("<br>", unsafe_allow_html=True)
        search_button = st.button("🔍 Smart Search", type="primary", use_container_width=True)
    
    # Search execution
    if search_button and search_query:
        if 'total_searches' not in st.session_state:
            st.session_state.total_searches = 0
        st.session_state.total_searches += 1
        
        perform_search(broll_lib, search_query, search_my_sources, search_youtube, search_web)
    
    # Display results if they exist
    if st.session_state.search_results and st.session_state.current_query:
        all_results = st.session_state.search_results
        current_query = st.session_state.current_query
        
        # Results summary with insights
        col1, col2 = st.columns([2, 1])
        with col1:
            st.success(f"🎯 Found {len(all_results)} results for '{current_query}'")
        with col2:
            if all_results:
                direct_matches = len([r for r in all_results if r.get('_match_type') == 'direct'])
                semantic_matches = len([r for r in all_results if r.get('_match_type') == 'semantic'])
                st.info(f"🎯 {direct_matches} direct • 🧠 {semantic_matches} semantic")
        
        # Search insights
        display_search_insights(current_query, all_results)
        
        # Determine which tabs to show based on results
        tabs_to_show = []
        tab_names = []
        
        tabs_to_show.append("all")
        tab_names.append("🔍 All Results (Ranked)")
        
        if any(r['source_type'] == 'my_sources' for r in all_results):
            tabs_to_show.append("my_sources")
            tab_names.append("📁 My Sources")
        
        if any(r['source_type'] == 'youtube' for r in all_results):
            tabs_to_show.append("youtube")
            tab_names.append("📺 YouTube")
        
        if any(r['source_type'] == 'web' for r in all_results):
            tabs_to_show.append("web")
            tab_names.append("🌐 Web")
        
        # Create dynamic tabs
        if len(tab_names) == 2:
            tab1, tab2 = st.tabs(tab_names)
            tabs = [tab1, tab2]
        elif len(tab_names) == 3:
            tab1, tab2, tab3 = st.tabs(tab_names)
            tabs = [tab1, tab2, tab3]
        elif len(tab_names) == 4:
            tab1, tab2, tab3, tab4 = st.tabs(tab_names)
            tabs = [tab1, tab2, tab3, tab4]
        else:
            tab1 = st.tabs(tab_names)[0]
            tabs = [tab1]
        
        # Display content for each tab
        for i, (tab_type, tab) in enumerate(zip(tabs_to_show, tabs)):
            with tab:
                if tab_type == "all":
                    st.markdown("### 🎯 All Results (Sorted by Relevance)")
                    st.caption("Results are automatically sorted by AI relevance scoring - direct matches first, then keyword matches, then semantic matches")
                    display_results_section_smooth(all_results, "all", show_all=True)
                
                elif tab_type == "my_sources":
                    my_source_results = [r for r in all_results if r['source_type'] == 'my_sources']
                    st.subheader(f"📁 Defined Sources ({len(my_source_results)} results)")
                    
                    # Group by source name
                    grouped_results = defaultdict(list)
                    for result in my_source_results:
                        grouped_results[result.get('source_name', 'Unknown')].append(result)
                    
                    result_idx = 0
                    for source_name, results in grouped_results.items():
                        st.markdown(f"**📁 {source_name} ({len(results)} results)**")
                        for result in results:
                            result['_display_id'] = f"my_{result_idx}"
                            display_search_result(result, 'my_sources')
                            result_idx += 1
                        if len(grouped_results) > 1:
                            st.divider()
                
                elif tab_type == "youtube":
                    youtube_results = [r for r in all_results if r['source_type'] == 'youtube']
                    st.subheader(f"📺 YouTube ({len(youtube_results)} results)")
                    st.caption("Results ranked by semantic relevance to your search query")
                    display_results_section_smooth(youtube_results, "youtube", 5)
                
                elif tab_type == "web":
                    web_results = [r for r in all_results if r['source_type'] == 'web']
                    st.subheader(f"🌐 Web Libraries ({len(web_results)} results)")
                    st.caption("Curated sources with semantic keyword matching")
                    display_results_section_smooth(web_results, "web", 3)
    
    # Help section
    with st.expander("ℹ️ How Semantic Search Works", expanded=False):
        st.markdown("""
        ### 🧠 AI-Enhanced Search Features
        
        **Keyword Expansion:**
        - Your search terms are automatically expanded with related concepts
        - Example: "business" → includes "corporate", "office", "meeting", "professional"
        
        **Match Types:**
        - 🎯 **Direct Match**: Exact query found in title/description
        - 🔑 **Keyword Match**: Original search terms found
        - 🧠 **Semantic Match**: Related concepts and synonyms found
        
        **Smart Ranking:**
        - Results are scored based on relevance to your query
        - Direct matches appear first, followed by keyword and semantic matches
        - Higher scores indicate better relevance to your search
        
        **Enhanced Query Processing:**
        - Searches use expanded keywords for better coverage
        - Semantic relationships improve result quality
        - Fuzzy matching catches similar terms you might have missed
        """)

if __name__ == "__main__":
    main()
