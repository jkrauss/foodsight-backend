# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.11.3
#   kernelspec:
#     display_name: 'Python 3.7.9 64-bit (''.venv'': venv)'
#     name: python3
# ---

# %%
import datetime as dt
import pandas as pd
import holidays
import os



# %%
### SCRIPT CELL - DON'T RUN IN NOTEBOOK


def run() :
    # change working directory to where this file lives
    os.chdir(os.path.dirname(os.path.abspath(__file__)))


    # %%
    # start with the dates from 2000 - 2030
    start_date = dt.datetime(2000, 1, 1, 0, 0, 0)
    day_delta = dt.timedelta(days=1)

    dates = list()

    d = start_date
    for i in range(365*30+8):
        dates.append(d)
        d += day_delta

    date_dim = pd.DataFrame(columns=['date'], data = dates)
    #date_dim

    # %%
    # year, month, day, week, weekday
    date_dim['year'] = date_dim.date.apply(lambda x: x.year)
    date_dim['month'] = date_dim.date.apply(lambda x: x.month)
    date_dim['day'] = date_dim.date.apply(lambda x: x.day)
    date_dim['week'] = date_dim.date.apply(lambda x: x.isocalendar()[1]) # mon-1 sun-7
    date_dim['weekday'] = date_dim.date.apply(lambda x: x.isoweekday()) # mon-1 sun-7

    # season
    def season(x):
        """
            input month as int
            returns season: spring, summer, fall, winter, undefined
        """
        if x in (3,4,5):
            return 'spring'
        elif x in (6,7,8):
            return 'summer'
        elif x in (9,10,11):
            return 'fall'
        elif x in (12,1,2):
            return 'winter'
        else:
            return 'undefined' 
    date_dim['season'] = date_dim.month.apply(lambda x: season(x))

    #date_dim

    # %%
    # now holidays in Hessen/HE, Germany, weekends and is_free_day

    # TODO: Generate features like same day last year, week, month, last 7 days

    # TODO: Add manually Rosenmontag, Faschingsdienstag, Aschermittwoch, Helloween (31.10.) ...e.g. from https://www.schulferien.org/deutschland/feiertage/2021/
    # TODO: Add Schulferien in HE
    # TODO: Add Verkaufsoffene Sonntage
    # TODO: Add corona-shops-closed
    # TODO: Add coutry-wide corona-incidence
    # TODO: Expand / duplicate HE and RP

    he_holidays = holidays.CountryHoliday('DE', prov='HE', years=date_dim.year.unique())
    rp_holidays = holidays.CountryHoliday('DE', prov='HE', years=date_dim.year.unique())
    hdays = he_holidays

    def holiday_name(d, h):
        """
            input a date and a holidays-dict
            output the name of the holiday or None
        """
        try:
            hol_name = h[d]
            if hol_name == 'Christi Himmelfahrt, Erster Mai':
                hol_name = 'Erster Mai'
            return hol_name
        except:
            return None

    date_dim['is_holiday'] = date_dim.date.apply(lambda x: x in hdays)
    date_dim['holiday_name'] = date_dim.date.apply(lambda x: holiday_name(x, hdays))
    date_dim['is_weekend'] = date_dim.weekday.apply(lambda x: x in (6,7))
    date_dim['is_free_day'] = date_dim.is_holiday | date_dim.is_weekend
    date_dim['is_shops_closed'] = date_dim.is_holiday | date_dim.weekday.apply(lambda x: x==7)

    date_dim #.groupby('is_weekend').count()

    # %%
    # date_dim.to_csv('pipeline/data/0_raw/date_dimension.csv', index=False)
    os.system('pwd')
    date_dim.to_csv('data/0_raw/date_dimension.csv', index=False)

    # %%
    # no more transformation required, therefore write also to /1_trans/
    #date_dim.to_csv('pipeline/data/1_trans/date_dimension.csv', index=False)
    date_dim.to_csv('data/1_trans/date_dimension.csv', index=False)

# %%

# %%
### SCRIPT CELL - DON'T RUN IN NOTEBOOK

if __name__ == '__main__':
    # run this step
    run()
