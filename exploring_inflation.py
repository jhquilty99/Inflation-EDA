from pickle import GLOBAL
from select import select
from unicodedata import name
import pandas as pd
import yfinance
from datetime import date
from datetime import datetime
from datetime import timedelta
import yaml
import numpy as np
import holidays
import draw_functions
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
def get_inflation_data(start_year: int, end_year: int, series: Optional[str] = 'CUUR0000SA0', series_name: Optional[str] = 'INFLATION') -> pd.DataFrame:
    # This data source also contains Ohio real estate inflation data
    parameters = json.dumps({"registrationkey":"913a29444d3849e58aaa8f651a4ceec6","seriesid":[series],"startyear":start_year,"endyear":end_year})
    headers = {'Content-type': 'application/json'}
    response = json.loads(requests.post('https://api.bls.gov/publicAPI/v2/timeseries/data/', data = parameters, headers = headers).text)
    inflation_df = pd.DataFrame.from_records(response['Results']['series'][0]['data'])
    function = lambda x: datetime.strptime(x['periodName'] + "," + x['year'], '%B,%Y')
    inflation_df.index=inflation_df.apply(function, axis = 1)
    inflation_df[series_name] = inflation_df['value'].astype(float)
    reindexed_inflation_df = inflation_df[series_name].reindex(pd.date_range(start=inflation_df[series_name].index.min(),
                                                  end=date(end_year, 12, 31),
                                                  freq='1D'))
    reindexed_inflation_df = reindexed_inflation_df.interpolate(method='time', limit_direction='forward')
    return(reindexed_inflation_df.to_frame(name=series_name))

def join_inflation_data(dataframe: pd.DataFrame, inflation: pd.DataFrame) -> pd.DataFrame:
    dataframe = pd.merge(dataframe, inflation, how='left', left_index=True, right_index=True)
    dataframe.dropna(how='all', inplace=True)
    dataframe[inflation.columns[0]] = dataframe[inflation.columns[0]].fillna(method="ffill")
    return(dataframe)

def normalize_data(df: pd.DataFrame, position: int = 0) -> pd.DataFrame:
    beg = df.iloc[-position]
    return df/beg

def get_data(start_year, end_year):
    # Retrieve data
    overall_cpi = get_inflation_data(start_year, end_year,'CUUR0000SA0','Overall CPI')
    urban_nsa = get_inflation_data(start_year, end_year,'CUUR0000SAH1','Urban Shelter Not Seasonally Adjusted')
    urban_sa = get_inflation_data(start_year, end_year,'CUSR0000SAH1','Urban Shelter Seasonally Adjusted')
    midwest_cpi = get_inflation_data(start_year, end_year,'CUURS200SA0','Midwest CPI')
    mid_atlantic_urban_nsa = get_inflation_data(start_year, end_year,'CUUR0120SAH1','Mid-Atlantic Shelter Not Seasonally Adjusted')
    midwest_urban_nsa = get_inflation_data(start_year, end_year,'CUUR0200SAH1','Midwest Shelter Not Seasonally Adjusted')
    # Join data
    all_inflation_data = join_inflation_data(overall_cpi, urban_nsa)
    all_inflation_data = join_inflation_data(all_inflation_data, urban_sa)
    all_inflation_data = join_inflation_data(all_inflation_data, mid_atlantic_urban_nsa)
    all_inflation_data = join_inflation_data(all_inflation_data, midwest_urban_nsa)
    return(join_inflation_data(all_inflation_data, midwest_cpi))

def compare_regions(regions, start_year, end_year, type = None):
    df = pd.DataFrame()
    k = 0
    for region in regions:
        region_dict = inflation_dictionary[region]
        for i in region_dict:
            new_data = get_inflation_data(start_year, end_year, region_dict[i], region + ' ' + i)
            if k == 0:
                df = new_data
                k += 1
            else: 
                df = join_inflation_data(df, new_data)
    if type is None:
        inflation_figure(df)
    elif type == 'Normal':
        normalized_inflation_figure(df)
    elif type == 'Derived':
        derived_inflation_figure(df)
    elif type == 'Ratio':
        ratio_figure(df, regions)
    else:
        return(f'Type, {type} not found')
    

def inflation_figure(figure_values):
    fig = px.line(figure_values, labels={'value':'$ Value', 'index':'Trading Date', 'variable':'Equity'})
    fig.show()

def normalized_inflation_figure(figure_values):
    figure_values = normalize_data(figure_values)
    fig = px.line(figure_values, labels={'value':'$ Value', 'index':'Trading Date', 'variable':'Equity'})
    fig.show()

def derive_data(dataframe):
    dataframe.dropna(how='all', inplace = True)
    return(dataframe.diff().rolling(60).mean())

def derived_inflation_figure(figure_values):
    figure_values = derive_data(figure_values)
    fig = px.line(figure_values, labels={'value':'$ Value', 'index':'Trading Date', 'variable':'Equity'})
    fig.show()

def ratio_figure(figure_values, regions):
    df = pd.DataFrame()
    for reg in regions:
        df[reg + ' Rent to CPI Ratio'] = figure_values[reg + ' ' + 'Urban Rent']/figure_values[reg + ' ' + 'CPI']
        df[reg + ' House to CPI Ratio'] = figure_values[reg + ' ' + 'Urban Housing']/figure_values[reg + ' ' + 'CPI']
        df[reg + ' House to Rent Ratio'] = figure_values[reg + ' ' + 'Urban Housing']/figure_values[reg + ' ' + 'Urban Rent']
    normalized_inflation_figure(df)
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
