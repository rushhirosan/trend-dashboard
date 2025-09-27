import base64
import time
from datetime import date, datetime, timedelta

import pandas as pd
import altair as alt
import streamlit as st
import isodate

from apiclient.discovery import build
import youtube_dl


# Search trend by region
@st.cache
def search_trend(youtube, region='US', max_results=5):
    trend_response = youtube.videos().list(
        part='id,snippet,contentDetails,statistics',
        chart='mostPopular',
        regionCode=region,
        maxResults=max_results,
        fields='items(id, snippet(title, channelTitle),\
            contentDetails(duration),\
            statistics(viewCount))'
    ).execute()

    video_responses = list()

    for tr in trend_response['items']:
        v_id = tr['id']
        v_ctitle = tr['snippet']['channelTitle']
        v_title = tr['snippet']['title']
        v_duration = tr['contentDetails']['duration']
        v_viewcount = tr['statistics']['viewCount']

        if v_duration == 'P0D':  # TODO: Unusual format, just ignore this.
            video_duration_sec = 0
        else:
            video_duration_sec = _convert_date_format(v_duration)

        v_duration_sec = str(timedelta(seconds=int(video_duration_sec)))

        video_response_map = dict(
            v_id=v_id,
            v_ctitle=v_ctitle,
            v_title=v_title,
            v_duration=v_duration_sec,
            v_viewcount=int(v_viewcount)
        )

        video_responses.append(video_response_map)

    trend_video_df = pd.DataFrame(video_responses)
    return trend_video_df


# Search by query from the entire youtube
@st.cache
def search_topn(youtube, q='', published_after_date='', max_results=10):
    """
    This function is to only get video id and channel id
    """
    query_response = youtube.search().list(
        q=q,
        part="id,snippet",
        order='viewCount',
        type='video',
        publishedAfter=published_after_date,
        maxResults=max_results
    ).execute()

    query_responses = list()
    if len(query_response['items']) == 0:
        return None
    else:
        for qr in query_response['items']:
            item_map = dict()
            item_map['v_id'] = qr['id']['videoId']
            item_map['channel_id'] = qr['snippet']['channelId']
            query_responses.append(item_map)

    query_video_df = pd.DataFrame(query_responses)
    return query_video_df


# Search videos by query above
@st.cache
def search_topn_videos(youtube, query_videos):
    """
    Grab details of the videos queried above.
    """
    v_ids = ','.join(query_videos['v_id'][:])

    video_response = youtube.videos().list(
        part='id,snippet,contentDetails,statistics',
        id=v_ids,
        fields='items(id, snippet(title, publishedAt),\
        contentDetails(duration),\
        statistics(viewCount, likeCount, dislikeCount, commentCount))'
    ).execute()

    return _convert_video_ids(video_response, query_videos)


# Converting date format of video duration
def _convert_date_format(video_duration):
    """
    ISO 8601: PTXXHYYMZZS -> HHMMDD -> total seconds
    """
    video_duration_seconds = 0
    if video_duration == 'P0D':
        pass
    else:
        video_duration_td = isodate.parse_duration(video_duration)
        video_duration_seconds = video_duration_td.total_seconds()
    return video_duration_seconds


# Convert video ids to dataframe
def _convert_video_ids(video_response, query_videos):
    """
    Merge query_videos with details
    """
    queried_videos = list()

    for vr in video_response['items']:
        v_id = vr['id']
        v_title = vr['snippet']['title']
        v_duration = vr['contentDetails']['duration']
        if vr['statistics'].get('likeCount', 0):
            v_likes = vr['statistics']['likeCount']
        # if i['statistics'].get('dislikeCount', 0): # dislike not cared anymore
        #     v_dislikes = i['statistics']['dislikeCount']
        if 'commentCount' in vr['statistics']:
            if vr['statistics'].get('commentCount', 0):
                v_commentcount = vr['statistics']['commentCount']
        else:
            v_commentcount = '0'
        v_publised_at = vr['snippet']['publishedAt']
        if vr['statistics'].get('viewCount', 0):
            v_viewcount = vr['statistics']['viewCount']

        video_duration_sec = _convert_date_format(v_duration)
        v_duration_sec = str(timedelta(seconds=int(video_duration_sec)))

        queried_video_map = dict(
            v_id=v_id,
            v_title=v_title,
            v_duration=v_duration_sec,
            v_likes=v_likes,
            # vdislikes=v_dislikes,
            v_commentcount=v_commentcount,
            v_pubsliedat=v_publised_at,
            v_viewcount=int(v_viewcount)
        )

        queried_videos.append(queried_video_map)

    queried_video_df = pd.DataFrame(queried_videos)
    queried_video_res_df = pd.merge(query_videos, queried_video_df, on='v_id')

    return queried_video_res_df


# Draw topn chart
def draw_topn_chart(df_topn_videos):
    c = alt.Chart(df_topn_videos).mark_bar().encode(
        alt.X('v_viewcount'),
        alt.Y('v_title:N', sort=alt.EncodingSortField(
            field='Title',
            op='count',
            order='ascending'))
        ).properties(
            width=800,
            height=500)
    return c


#############################
# Channel id search section
#############################
@st.cache
def get_playlistitem_from_channel(youtube, cid):
    ch_response = youtube.channels().list(
        part='id,snippet,contentDetails,statistics',
        id=cid
    ).execute()

    ch_item = ch_response['items']
    ch_playlist_id = \
        ch_item[0]['contentDetails']['relatedPlaylists']['uploads']

    return _get_playlist_of_channel(youtube, ch_playlist_id)

@st.cache
def _get_playlist_of_channel(youtube, ch_playlist_id):
    ch_playlistitem_responses = []

    ch_playlistitem_response = youtube.playlistItems().list(
        part='id,snippet,contentDetails,status',
        playlistId=ch_playlist_id
    ).execute()

    ch_playlistitem_responses.append(ch_playlistitem_response)

    npt = ch_playlistitem_response.get('nextPageToken', 0)
    if npt:
        npt = ch_playlistitem_response['nextPageToken']
    else:
        npt = None

    while npt:
        ch_playlistitem_response_next = youtube.playlistItems().list(
            part='id,snippet,contentDetails,status',
            playlistId=ch_playlist_id,
            pageToken=npt
        ).execute()
        ch_playlistitem_responses.append(ch_playlistitem_response_next)
        npt = ch_playlistitem_response_next.get('nextPageToken', 0)
        if npt:
            npt = ch_playlistitem_response_next['nextPageToken']
        else:
            npt = None

    return ch_playlistitem_responses

@st.cache
def get_video_df_from_channel(youtube, playlist_items):
    videos = _get_videos_from_playlistitems(playlist_items)
    videos_amt = len(videos)
    cnt = 0
    max_page = 50
    ch_list = list()

    while videos_amt >= 0:
        v_ids = ','.join(videos[cnt:max_page+cnt])
        ch_video_response = youtube.videos().list(
            part='id,snippet,contentDetails,statistics',
            id=v_ids,
            fields='items(id, snippet(title, channelTitle),\
            contentDetails(duration),\
            statistics(viewCount))'
            ).execute()
        channel_df = _make_df(ch_video_response, ch_list)
        cnt += max_page
        videos_amt -= max_page

    return channel_df


def _get_videos_from_playlistitems(playlistitems):
    v_playlist = list()

    for p in playlistitems:
        for i in p['items']:
            v_playlist.append(i['contentDetails']['videoId'])

    return v_playlist


def _make_df(video_response, res_list):

    for i in video_response['items']:
        v_id = i['id']
        v_ctitle = i['snippet']['channelTitle']
        v_title = i['snippet']['title']
        v_duration = i['contentDetails']['duration']
        v_viewcount = i['statistics']['viewCount']

        video_duration_sec = _convert_date_format(v_duration)
        v_duration_sec = str(timedelta(seconds=int(video_duration_sec)))

        video_map = dict(
            v_id=v_id,
            v_ctitle=v_ctitle,
            v_title=v_title,
            v_duration=v_duration_sec,
            v_viewcount=int(v_viewcount)
        )

        res_list.append(video_map)

    response_df = pd.DataFrame(res_list)
    return response_df


# Download as csv
def download_as_csv(data):
    """
    Convert dataframe to csv for download
    """
    csv_file = data.to_csv()
    time_str = time.strftime("%Y%m%d-%H%M%S")
    b64 = base64.b64encode(csv_file.encode()).decode()
    new_filename = "new_text_file_{}_.csv".format(time_str)
    st.markdown("#### Download this table data ###")
    href = f'<a href="data:file/csv;base64,{b64}" ' \
           f'download="{new_filename}">Click Here!!</a>'
    st.markdown(href, unsafe_allow_html=True)


def downlaod_as_mp3(video_id):
    """
    Download a video from youtube as mp3
    """
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': "%(title)s" + '.%(ext)s',
        'postprocessors': [
            {'key': 'FFmpegExtractAudio',
             'preferredcodec': 'mp3',
             'preferredquality': '192'},
            {'key': 'FFmpegMetadata'},
        ],
    }

    ydl = youtube_dl.YoutubeDL(ydl_opts)
    ydl.extract_info(
        f"https://www.youtube.com/watch?v={video_id}", download=True)

#############################
# Main app with UI
#############################
def app():
    """
    Main app
    """
    # Configuration
    ##############################
    DEVELOPER_KEY = st.secrets['youtube_secrets']['KEY'][0]
    YOUTUBE_API_SERVICE_NAME = "youtube"
    YOUTUBE_API_VERSION = "v3"
    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION,
                    developerKey=DEVELOPER_KEY, cache_discovery=False)
    ##############################

    # Title
    st.title(f'▶️ YouTube trend')
    st.markdown("""
        ## This page uses youtube data api to grab top N popular videos.\n
        If you would like to dig a bit of channels, you will be able to 
        do it by querying a channel id.\n  
        Additionally, you can enjoy a video by a video id you found.
        Enjoy! :smiley:
        
        __Recommend: Search range is set to the most recent one month.__
        
        ---
    """)

    # Streamlit UI columns
    col1, col2 = st.columns([1.5, 1.5])

    with col1:
        st.write('Trending search')
        market = st.selectbox(
            'Choose region', (
                '',
                'US:United States',
                'JP:Japan',
                'UK:United Kingdom',
                'ID:India',
                'AU:Australia',
                'DE:Germany',
            )
            , index=0
        )
        st.write('\n')
        st.write('\n')
        st.write('\n')
        st.write('\n')
        st.write('\n')
        st.write('\n')

    with col2:
        st.write('Query search')
        q = st.text_input('Please input your query to search')
        thirty_days_before = (date.today() - timedelta(days=30)).isoformat()
        y, m, d = map(int, thirty_days_before.split('-'))
        after_day = st.date_input(
            "Published after", datetime(y, m, d), key='youtube')
        after_day = datetime.fromisoformat(str(after_day))
        after_day = datetime.strftime(after_day, '%Y-%m-%dT%H:%M:%S.%fZ')

    # Common components
    top_n = st.slider('Search result volume: You can set N up until 50. '
                       'if you set 5, you will get 5 results', 1, 50, 10)
    search_btn = st.button("Search")

    search_res_field = st.empty()
    search_res_field2 = st.empty()
    # search_res_field.markdown("""
    #     ## `Your search result appears here!`
    # """)

    # Button actions: Query search whether or not query is input
    if search_btn:
        search_res_field.empty()
        search_res_field2.empty()
        # Run trending search when selectbox is set to one of the options.
        if len(market) != 0 and len(q) == 0:
            market = market[:2]
            try:
                df_videos = search_trend(
                    youtube, region=market, max_results=top_n)
                if df_videos is None:
                    st.error('No items. Please query differently')
                c = draw_topn_chart(df_videos)
                search_res_field.altair_chart(c)
                search_res_field2.dataframe(df_videos)
            except IOError:
                st.error('Search error')
        # Run query search when selectbox is set to default, none.
        else:
            try:
                query_videos = search_topn(
                    youtube, q, after_day, max_results=top_n)
                if query_videos is None:
                    st.error('No items. Please query differently')
                queried_video_res_df = search_topn_videos(youtube, query_videos)
                query_chart = draw_topn_chart(queried_video_res_df)
                search_res_field.altair_chart(query_chart)
                search_res_field2.dataframe(queried_video_res_df)
            except IOError:
                st.error('Search error')

    ############################################################################

    # Channel ID and Video ID
    st.markdown("""
        ---
        ## You can search what's popular in the channel here :tv:\n
    """)

    # Channel_id section
    channel_id = st.text_input('Please input a channel id to search')
    channel_btn = st.button("Channel search")

    # Empty fields
    channel_search_res_field = st.empty()
    # channel_search_res_field.markdown("""
    #     ## `Your channel id search result appears here!`
    # """)

    # Channel search
    if channel_btn and len(channel_id) != 0:
        channel_search_res_field.empty()
        try:
            vsi = get_playlistitem_from_channel(youtube, channel_id)
            df3 = get_video_df_from_channel(youtube, vsi)
            channel_search_res_field.dataframe(
                df3.sort_values('vviewcount', ascending=False))
            download_as_csv(df3)
        except IOError:
            st.error('Video rendering error')

    st.markdown("""
        ---
        ## Also, you can watch a video and download as mp3 :video_camera:\n
    """)


    # Video_id section
    video_id = st.text_input('Please input a video id to watch')
    url = f'https://youtu.be/{video_id}'
    watch_btn = st.button("Watch")

    # Empty fields
    video_res_field = st.empty()
    # video_res_field.markdown("""
    #     ## `A video appears here!`
    # """)

    if len(video_id) > 1 and watch_btn:
        video_res_field.empty()
        try:
            video_res_field.video(url)
            dl_btn = st.button("Download as mp3")
            if dl_btn:
                downlaod_as_mp3(video_id)
        except IOError:
            st.error('Video rendering error')