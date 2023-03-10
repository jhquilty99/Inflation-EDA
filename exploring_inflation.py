from pickle import GLOBAL
from select import select
from unicodedata import name
import pandas as pd
from datetime import date
from datetime import datetime
from datetime import timedelta
import numpy as np
import locale
import typing
import plotly.express as px
import dash_daq as daq
import json
import dash_bootstrap_components as dbc
import requests
import re
from typing import Tuple, Union, Optional, Dict, List

#'Countrywide Urban Shelter Seasonally Adjusted':'CUSR0000SAH1',

# 'Cleveland CPI':'CUUSA210SA0',
#                         'Cleveland Urban Rent':'CWURA210SAH1',
#                         'Cleveland Urban Housing':
#                         'Cleveland Housing':'CUURA210SAH'

# Get all the rent, overall CPI, and shelter inflation by market
# Markets include West, Midwest, South, Northeast
# All metrics should not be seasonally adjusted for all urban consumers

cw_dictionary = {'CPI':'CUUR0000SA0',
                'Urban Rent':'CUUR0000SAS2RS',
                'Urban Housing':'CUUR0000SAH'}

ne_dictionary = {'CPI':'CUUR0100SA0',
                'Urban Rent':'CUUR0100SAS2RS',
                'Urban Housing':'CUUR0100SAH'}

mw_dictionary = {'CPI':'CUURS200SA0',
                'Urban Rent':'CUUR0200SAS2RS',
                'Urban Housing':'CUUR0200SAH'}

so_dictionary = {'CPI':'CUUR0300SA0',
                'Urban Rent':'CUUR0300SAS2RS',
                'Urban Housing':'CUUR0300SAH'}

we_dictionary = {'CPI':'CUUR0400SA0',
                'Urban Rent':'CUUR0400SAS2RS',
                'Urban Housing':'CUUR0400SAH'}

inflation_dictionary = {'Countrywide':cw_dictionary,
                        'Midwest':mw_dictionary,
                        'West':we_dictionary,
                        'South':so_dictionary,
                        'Northeast':ne_dictionary
                        }
def get_inflation_data(start_year: int, end_year: int, series_dict: Optional[Dict[str, str]] = {'CUUR0000SA0':'Countrywide CPI'}) -> pd.DataFrame:
    inflation_df = pd.DataFrame()
    # This data source also contains Ohio real estate inflation data
    parameters = json.dumps({"seriesid":list(series_dict.keys()), "startyear":start_year, "endyear":end_year, "registrationkey":"913a29444d3849e58aaa8f651a4ceec6"})
    headers = {'Content-type': 'application/json'}
    response = requests.post('https://api.bls.gov/publicAPI/v2/timeseries/data/', data = parameters, headers = headers)
    response = json.loads(response.text)
    # Add each series data to dataframe
    i = 0
    for ser in series_dict:
        inflation_df[series_dict[ser]] = pd.DataFrame.from_records(response['Results']['series'][i]['data'])['value'].astype(float)
        i += 1
    # Get date field
    date_df = pd.DataFrame.from_records(response['Results']['series'][0]['data'])
    function = lambda x: datetime.strptime(x['periodName'] + "," + x['year'], '%B,%Y')
    inflation_df.index = date_df.apply(function, axis = 1)
    reindexed_inflation_df = inflation_df.reindex(pd.date_range(start=inflation_df.index.min(),
                                                  end=date(end_year, 12, 31),
                                                  freq='1D'))
    reindexed_inflation_df = reindexed_inflation_df.interpolate(method='time', limit_direction='forward')
    return(reindexed_inflation_df)

def normalize_data(df: pd.DataFrame, date: pd.Timestamp) -> pd.DataFrame:
    beg = df.loc[date]
    return df/beg

def get_all_data(start_year, end_year):
    series_dict = {}
    for region in inflation_dictionary:
        region_dict = inflation_dictionary[region]
        for name in region_dict:
            series_dict[region_dict[name]] = region + ' ' + name
    return(get_inflation_data(start_year, end_year, series_dict))

def compare_regions(inflation_df, regions, start_year, end_year, type = None):
    series = []
    for region in regions:
        region_dict = inflation_dictionary[region]
        for name in region_dict:
            series.append(region + ' ' + name)
    df = inflation_df[series]
    if type is None:
        inflation_figure(df, start_year, end_year)
    elif type == 'Normal':
        normalized_inflation_figure(df, start_year, end_year)
    elif type == 'Derived':
        derived_inflation_figure(df, start_year, end_year)
    elif type == 'Ratio':
        ratio_figure(df, regions, start_year, end_year)
    else:
        return(f'Type, {type} not found')
    

def inflation_figure(figure_values, start_year, end_year):
    fig = px.line(figure_values, labels={'value':'Value', 'index':'Date', 'variable':'Series'})
    fig.update_xaxes(type = 'date', range = [pd.Timestamp(year = start_year, month = 1, day = 1), pd.to_datetime(date.today())])
    fig.show()

def normalized_inflation_figure(figure_values, start_year, end_year):
    figure_values = normalize_data(figure_values, pd.Timestamp(year = start_year, month = 1, day = 1))
    fig = px.line(figure_values, labels={'value':'Value Normalized to Beginning of Time Period', 'index':'Date', 'variable':'Series'})
    fig.update_xaxes(type = 'date', range = [pd.Timestamp(year = start_year, month = 1, day = 1), pd.to_datetime(date.today())])
    fig.show()

def derived_inflation_figure(figure_values, start_year, end_year):
    figure_values.dropna(how='all', inplace = True)
    figure_values = figure_values.diff().rolling(60).mean()
    fig = px.line(figure_values, labels={'value':'60-Day Rolling Average of Change in Inflation', 'index':'Date', 'variable':'Series'})
    fig.update_xaxes(type = 'date', range = [pd.Timestamp(year = start_year, month = 1, day = 1), pd.to_datetime(date.today())])
    fig.show()

def ratio_figure(figure_values, regions, start_year, end_year):
    df = pd.DataFrame()
    for reg in regions:
        df[reg + ' Rent to CPI Ratio'] = figure_values[reg + ' ' + 'Urban Rent']/figure_values[reg + ' ' + 'CPI']
        df[reg + ' House to CPI Ratio'] = figure_values[reg + ' ' + 'Urban Housing']/figure_values[reg + ' ' + 'CPI']
        df[reg + ' House to Rent Ratio'] = figure_values[reg + ' ' + 'Urban Housing']/figure_values[reg + ' ' + 'Urban Rent']
    normalized_inflation_figure(df, start_year, end_year)
    #Normalizing the raw data before or after doesn't matter
    

# Test the hypothesis:
# It is best to buy a house when there is a lot of rent inflation and proportionally less shelter inflation
# High and low inflation can be tested against the CPI there 
# This would mean that rent is expensive however shelter is not that much more expensive
# This hypothesis could be tested against the average margins on rental properties following these times
# Also test the inverse hypothesis, low rent inflation and high shelter inflation
# Tasks:
# 1. Figure out the distinction between inflation in housing, shelter, and rent
# 2. Make a function that allows you to surf across different regions for their inflation data
# 3. Get the data for rental profit margins by region and time
