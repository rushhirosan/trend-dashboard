import re

import tweepy
import altair as alt
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

from datetime import date, datetime, timedelta
from wordcloud import WordCloud
from janome.tokenizer import Tokenizer

##############################
# THESE ARE FOR WORDCLOUD and mainly treatments for Japanese
##############################
def clean_alpha_text(tweet):
    tweet = tweet.lower()
    tweet = re.sub(r'@[a-z0-9_]\S+', '', tweet)
    tweet = re.sub(r'#[a-z0-9_]\S+', '', tweet)
    tweet = re.sub(r'&[a-z0-9_]\S+', '', tweet)
    tweet = re.sub(r'http[a-z0-9_]\S+', '', tweet)
    tweet = re.sub(r'[?!.,+;:$%&"]+', '', tweet)
    tweet = re.sub(r'rt[\s]+', '', tweet)
    # tweet = re.sub(r'\d+', '', tweet)
    tweet = re.sub(r'rt+', '', tweet)
    tweet = re.sub(r'\n+', '', tweet)
    tweet = re.sub(r'\$', '', tweet)
    #tweet = re.sub(r'http?:?\/\/S+', '', tweet)
    return tweet


def _clean_db_text(text):
    code_regex = re.compile(
        '[!"#$%&\'\\\\()*+,-./:;<=>?@[\\]^_`{|}~「」〔〕“”〈〉『』【】＆＊・（）＄＃＠。、？！｀＋￥％]')
    cleaned_text = code_regex.sub('', text)
    return cleaned_text


def tokenize_text(text):
    jt = Tokenizer()
    ex_words = []
    for tok in jt.tokenize(text):
        if '名詞' in tok.part_of_speech.split(','):
            ex_words.append(tok.surface)
    nouns = " ".join(map(str, ex_words))
    return _clean_db_text(nouns)


def detect_cjk(texts):
    cjk = False
    # KO
    if re.search("[\uac00-\ud7a3]", texts):
        return not cjk
    # JP
    elif re.search("[\u3040-\u30ff]", texts):
        return not cjk
    # CH
    elif re.search("[\u4e00-\u9FFF]", texts):
        return not cjk
    return cjk


def generate_wordcloud(df_text):
    all_tweets = ' '.join(
        tweet for tweet in df_text
    )
    if not detect_cjk(all_tweets):
        word_cloud = WordCloud()
        wc = word_cloud.generate(all_tweets)
    else:
        tokenized_tweets = tokenize_text(all_tweets)
        word_cloud = WordCloud(
            font_path='/System/Library/Fonts/ヒラギノ明朝 ProN.ttc',
            stopwords={
                "で", "の", "を", "て", "に", "を", "は", "とき", "と",
                "た", "ある", "が", "も", "さん"})
        wc = word_cloud.generate(tokenized_tweets)
    return wc


def prepare_wc_barchart(word_cloud):
    word_freq = pd.DataFrame.from_dict(data=word_cloud.words_,
                                       orient='index',
                                       columns=['freq'])
    word_freq = word_freq.head(20)
    word_freq.reset_index(inplace=True)
    word_freq = word_freq.rename(columns={'index': 'name'})
    return word_freq
##############################


def get_tweets(api, q, from_date, to_date, max_res):
    tweets_data = tweepy.Cursor(
        api.search_30_day,
        label='dev',
        query=q,
        fromDate=from_date,
        toDate=to_date,
    ).items(max_res)

    return _convert_tweets_tolist(tweets_data)


def _convert_tweets_tolist(tweets_data):
    tweets_list = []

    for t in tweets_data:
        if 'RT' in t.text:  # Excluding RT
            continue
        tweets_list.append(t)

    return tweets_list


def convert_tweets_to_df(tweets_data_list):
    tweets_list = []

    for t in tweets_data_list:
        tweet = dict()
        tweet['username'] = t.user.name
        tweet['content'] = t.text
        tweet['clean_content'] = clean_alpha_text(tweet['content'])
        tweet['link'] = \
            f'<a href="https://twitter.com/' \
            f'{t.user.screen_name}/status/{t.id}">link</a>'
        tweet['favourites_count'] = t.favorite_count
        tweet['retweet_count'] = t.retweet_count
        tweet['reply_count'] = t.reply_count
        tweet['quote_count'] = t.quote_count
        tweet['created_date'] = t.created_at
        tweets_list.append(tweet)

    tweets_df = pd.DataFrame(tweets_list)
    return tweets_df


def search_trend(api, woeid, exclude_hash, exclude_zero):
    ex_hash = exclude_hash
    
    if exclude_hash:
        ex_hash = 'hashtags'
    trends = api.get_place_trends(id=woeid, exclude=ex_hash)

    trend_list = list()
    for value in trends:
        for trend in value['trends']:
            trend_dict = dict()
            trend_dict['name'] = trend['name']
            trend_dict['volume'] = trend['tweet_volume']
            trend_dict['link'] = \
                f'<a target="_blank" href="{trend["url"]}">Link</a>'
            trend_list.append(trend_dict)

    trend_df = pd.DataFrame(trend_list)
    if exclude_zero:
        trend_df_clean = trend_df.dropna()
    else:
        trend_df_clean = trend_df.fillna(0)
    trend_df_clean['volume'] = trend_df_clean['volume'].astype('int')

    return trend_df_clean


def convert_df(df):
    return df.to_csv().encode('utf-8')


def download_df(df):
    st.write('\n')
    csv = convert_df(df)
    st.download_button(
        "Click to download",
        csv,
        "words.csv",
        "text/csv",
        key='download-csv'
    )


def app():
    """
    Main app
    """
    ##############################
    # KEY SET
    CONSUMER_KEY = st.secrets['twitter_secrets']['CONSUMER_KEY'][0]
    CONSUMER_SECRET = st.secrets['twitter_secrets']['CONSUMER_SECRET'][0]
    ACCESS_TOKEN = st.secrets['twitter_secrets']['ACCESS_TOKEN'][0]
    ACCESS_TOKEN_SECRET = st.secrets['twitter_secrets']['ACCESS_TOKEN_SECRET'][0]

    auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
    auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth)
    ##############################

    woe_ids = {
        'JP:Tokyo': 1118370,
        'US:New York': 2459115,
        'UK:London': 44418,
        'ID:New Delhi': 2295019,
        'AU:Sydney': 1105779,
        'GE:Berlin': 638242
    }

    # Streamlit UI
    st.title(f':eyeglasses: Twitter search')

    col1, col2 = st.columns([1.5, 1.5])

    # Trending search (No query)
    with col1:
        st.write("Trending search :chart_with_upwards_trend:")
        st.write("You can search what\'s hot in your region.")
        market = st.selectbox(
            'Choose region', (
                '',
                'JP:Tokyo',
                'US:New York',
                'UK:London',
                'ID:New Delhi',
                'AU:Sydney',
                'GE:Berlin',
            ))
        exclude_hash = False
        exclude_zero_vol = False
        ht_ck = st.checkbox('Exclude hashtags')
        zv_ch = st.checkbox('Exclude zero volume')
        if ht_ck:
            exclude_hash = True
        if zv_ch:
            exclude_zero_vol = True

    # Query search
    with col2:
        st.markdown('Query search :mag:')
        st.write("You can search tweets by a keyword.")
        q = st.text_input('Please input your query')
        # default 30 days
        thirty_days_before = (date.today() - timedelta(days=30)).isoformat()
        y, m, d = map(int, thirty_days_before.split('-'))
        from_date = st.date_input(
            "Tweeted from", datetime(y, m, d))
        from_date = datetime.fromisoformat(str(from_date))
        from_date = datetime.strftime(from_date, '%Y%m%d%H%M')
        # Twitter api does not allow today
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        y, m, d = map(int, yesterday.split('-'))
        to_date = st.date_input(
            "Tweeted to", datetime(y, m, d))
        to_date = datetime.fromisoformat(str(to_date))
        to_date = datetime.strftime(to_date, '%Y%m%d%H%M')
        max_res = st.slider(
            'Search result volume: You can set N up until 500. '
            'if you set 5, you will get 5 results.', 10, 500, 10
        )

    # Common option (word cloud)
    st.markdown("---")
    wc_ck = st.checkbox(
        'Show word cloud: Note that this option is for common usage'
    )

    # Search button
    if st.button('Search'):
        result_field = st.empty()
        if wc_ck:
            result_field_wc = st.empty()
            result_field_wc_chart = st.empty()
        if len(q) > 1:
            try:
                tweets_data_list = get_tweets(
                    api, q, from_date, to_date, max_res)
                tweet_df_ui = convert_tweets_to_df(tweets_data_list)
                tweet_df_ui = tweet_df_ui.sort_values(
                    'favourites_count', ascending=False
                )
                result_field.write(tweet_df_ui.to_html(
                    escape=False, index=False, justify="left"),
                    unsafe_allow_html=True)
                if wc_ck:
                    word_cloud = generate_wordcloud(
                        tweet_df_ui['clean_content']
                    )
                    plt.imshow(word_cloud)
                    plt.axis('off')
                    result_field_wc.pyplot(plt)
                    # Plotting barchart
                    word_freq = prepare_wc_barchart(word_cloud)
                    result_field_wc_chart.write(alt.Chart(word_freq).mark_bar().encode(
                        x=alt.X('name', sort=None),
                        y='freq'
                    ))
                download_df(tweet_df_ui)
            except IOError:
                st.error('Query search error')
        else:
            if wc_ck:
                result_field_wc = st.empty()
                result_field_wc_chart = st.empty()
            if market != '':
                woe_id = woe_ids[market]
                try:
                    trend_df_ui = search_trend(
                        api, woe_id, exclude_hash, exclude_zero_vol
                    )
                    trend_df_ui = trend_df_ui.sort_values(
                        'volume', ascending=False
                    )
                    result_field.write(trend_df_ui.to_html(
                        escape=False, index=False, justify="left"),
                        unsafe_allow_html=True)
                    if wc_ck:  # TODO: Resolve redunduncy here
                        word_cloud = generate_wordcloud(
                            trend_df_ui['name']
                        )
                        plt.imshow(word_cloud)
                        plt.axis('off')
                        result_field_wc.pyplot(plt)
                        # Plotting barchart
                        word_freq = prepare_wc_barchart(word_cloud)
                        result_field_wc_chart.write(
                            alt.Chart(word_freq).mark_bar().encode(
                                x=alt.X('name', sort=None),
                                y='freq'
                            ))
                    download_df(trend_df_ui)
                except IOError:
                    st.error('Search trend error')
            else:
                st.error('Please choose a region and try again')
