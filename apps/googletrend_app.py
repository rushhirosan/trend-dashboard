import pandas as pd
import streamlit as st

from datetime import date, datetime, timedelta
from pytrends.request import TrendReq


@st.cache_data
def get_trend(pyt, country):
    """
    Get trend
    """
    pn = country.lower()
    trend_results = pyt.trending_searches(pn=pn)

    trend_res_list = list()    

    for i in trend_results.values:
        trend_res_list.append(i[0])

    return trend_res_list


@st.cache_data
def trend_df(pyt, keywords, set_date):
    """
    Make trend dataframe
    """
    n = 0

    trend_list = list()

    while n < len(keywords):
        key_chk = keywords[n:n + 5]
        pyt.build_payload(
            key_chk,
            cat=0,
            timeframe=set_date,
            geo='',
            gprop='')
        df = pyt.interest_over_time()
        df = df[key_chk]
        trend_list.append(df)
        n += 5

    return trend_list

#############################
# Main app with UI
#############################


def app():
    """
    Main app
    """
    st.title(':chart_with_upwards_trend: Google trend search')
    selected_country = st.selectbox('What country would you like to search?',
                                    (
                                        '',
                                        'United_States',
                                        'Japan',
                                        'United Kingdom',
                                        'India',
                                        'Australia',
                                        'Germany'
                                    ))
    # These values for timezone may be wrong.
    tz_dict = {
                  'United_States': ['US', 360],
                  'Japan': ['JP', 540],
                  'United Kingdom': ['UK', 0],
                  'India': ['ID', 330],
                  'Australia': ['AU', 570],
                  'Germany': ['DE', 60],
    }


    # n days before
    sixty_days_before = (date.today() - timedelta(days=60)).isoformat()
    y, m, d = map(int, sixty_days_before.split('-'))
    trend_after_day = st.date_input(
        "Trend after", datetime(y, m, d), key='gtrend')
    trend_after_day = datetime.fromisoformat(str(trend_after_day))
    trend_after_day = datetime.strftime(trend_after_day, '%Y-%m-%d')

    # today for comparison
    d_today = date.today()
    end_date = d_today.strftime('%Y-%m-%d')  # today
    to_date = end_date
    set_date = trend_after_day + ' ' + to_date

    if selected_country != '':
        hl = tz_dict[selected_country][0]
        tz = tz_dict[selected_country][1]
        py_trends = TrendReq(hl=hl, tz=tz)
        keywords = get_trend(py_trends, selected_country)
        trends = trend_df(py_trends, keywords, set_date)
        t_df = trends[0]

        for i in range(1, len(trends)):
            cols = trends[i].columns.difference(t_df.columns)
            t_df = pd.merge(
                t_df,
                trends[i][cols],
                how='inner',
                left_index=True,
                right_index=True)

        trend_words = ''

        for i, word in enumerate(keywords, start=1):
            word = "".join(list(word.split()))
            trend_link = "https://www.google.co.jp/search?q=" + word
            trend_words += f'{i}: [{word}]({trend_link}) '

        t = f'''
        ## Trend keywords :key:
    
        {trend_words}
        '''
        st.markdown(t)
        selected_words = st.multiselect(
            "Select words",
            keywords,
            [keywords[0], keywords[1], keywords[2], keywords[3], keywords[4]]
        )
        t_df = t_df.loc[:, selected_words[:]]
        st.line_chart(t_df)
    else:
        st.info('Please choose a country')


if __name__ == "__main__":
    app()


