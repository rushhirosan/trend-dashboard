import pandas as pd
import spotipy
import streamlit as st


@st.cache
def get_search_results(spotify, q, type='show', market='US'):
    """
    Search by query
    """
    search_results = spotify.search(q=q, type=type, market=market)
    results_list = []
    type += 's'

    for item in search_results[type]['items']:
        item_dict = dict()
        item_dict['uri'] = item['uri'].split(':')[2]
        item_dict['show_name'] = item['name']
        item_dict['description'] = item['description']
        results_list.append(item_dict)

    search_result_df = pd.DataFrame(results_list)
    return search_result_df


def _convertMillis(millis):
    """
    Convert millseconds to HH:MM:SS
    """
    millis = int(millis)
    seconds = (millis/1000) % 60
    seconds = int(seconds)
    minutes = (millis/(1000*60)) % 60
    minutes = int(minutes)
    hours = (millis/(1000*60*60)) % 24
    hours = int(hours)

    return hours, minutes, seconds


@st.cache
def get_episodes(spotify, id, market='US'):
    """
    Get episode by showid
    """
    episode_results = spotify.show_episodes(id, market=market)

    episode_list = []

    for item in episode_results['items']:
        item_dict = dict()
        item_dict['uri'] = item['uri'].split(':')[2]
        item_dict['episode_name'] = item['name']
        #item_dict['description'] = item['description'] # Not necessary
        item_dict['duration'] = item['duration_ms']
        millis = item['duration_ms']
        h, m, s = _convertMillis(millis)
        item_dict['duration'] = '{0:02}:{1:02}:{2:02}'.format(h, m, s)
        item_dict['release_date'] = item['release_date']
        item_dict['link'] = item['external_urls']['spotify']
        episode_list.append(item_dict)

    episode_df = pd.DataFrame(episode_list)
    return episode_df

# Make a table text clickable
def make_clickable(url, text):
    return f'<a target="_blank" href="{url}">{text}</a>'


def app():
    """
    Main app
    """
    # Configuration
    ##############################
    client_id = st.secrets['spotify_secrets']['CLIENT_ID'][0]
    client_secret = st.secrets['spotify_secrets']['CLIENT_SECRET'][0]
    client_credentials_manager = spotipy.oauth2.SpotifyClientCredentials(
        client_id, client_secret)
    spotify = spotipy.Spotify(
        client_credentials_manager=client_credentials_manager)
    ##############################
    # UI
    st.title(f':radio: Spotify search')
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        q = st.text_input('Please input your query')
    with col2:
        media_type = st.selectbox('Choose type', ('show', 'artist'))
    with col3:
        market = st.selectbox('Choose market',
                              ('US', 'JP', 'ID', 'AU', 'GE')) # UK does not work for some reason
    if st.button('Search') and len(q) > 1:
        try:
            search_result_df_ui = get_search_results(
                spotify, q, type=media_type, market=market)
            st.dataframe(search_result_df_ui)
        except IOError:
            st.error('Search error')

    q2 = st.text_input('Or if you would like to search show id directly, '
                       'Please input a show id.')

    if st.button('Get episodes') and len(q2) > 1:
        try:
            episode_df_ui = get_episodes(spotify, q2, market=market)
            episode_df_ui['link'] = \
                episode_df_ui['link'].apply(make_clickable, args=('Link',))
            st.write(episode_df_ui.to_html(
                escape=False, index=False, justify="left"),
                unsafe_allow_html=True)
        except IOError:
            st.error('Search error')