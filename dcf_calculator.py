import pandas as pd
import numpy as np
import traceback

from selenium import webdriver
from dotenv import load_dotenv
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

from yahooquery import Ticker

import time
import re
import os
import datetime
import signal
import sys
import smtplib

# Setting up of the web driver (change location depending on where the binary is stored)
options = Options()
is_headless = True #if os.getenv("IS_HEADLESS") == "True" else False
options.headless = is_headless
if os.name != "nt":
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument("start-maximized")
    options.add_argument("disable-infobars")
    options.add_argument("--disable-extensions")

# [James Bond] Include modifying user-agent header to fit the simulated browser
if os.name == "nt":
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36")
    browser_driver = "chromedriver.exe"
else:
    options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36")
    browser_driver = "/usr/local/bin/chromedriver"

# [James Bond] More evasion techniques
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_argument("window-size=1280,800")

driver = webdriver.Chrome(browser_driver, options=options)

# Go to macrotrends page
def get_macrotrends_correct_url(company:str):
    print("Getting Macrotrends formatted URL")
    driver.get("https://www.macrotrends.net/stocks/charts/" + company + "/")
    time.sleep(1)
    print(driver.current_url)
    return driver.current_url

def get_net_cash_flow_history(url):
    print("Getting Net cash flow data from Macrotrends")
    driver.get(url + "net-cash-flow")
    driver.find_element_by_class_name('historical_data_table')
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")
    data_table = soup.find("td", {"style": "text-align:center"}).parent.parent.find_all("tr")
    data_dictionary = {}
    for data in data_table:
        parsed_data = data.text.split("\n")
        data_dictionary[parsed_data[1]] = parsed_data[2]
    return data_dictionary

def get_fcf_yoy_growth(fcf_dict, dcf_discount_rate):
    fcf_yoy = []
    fcf_yoy.append(None)
    year_today = datetime.datetime.now().year
    #Get historical fcf growth
    for year in range(year_today-9, year_today):
        fcf_before = fcf_dict.get(str(year-1), None)
        fcf_after = fcf_dict.get(str(year), None)
        if fcf_before == None or fcf_after == None:
            fcf_yoy.append(None)
        else:
            fcf_before = int(fcf_before.replace(",", "").replace("$", ""))
            fcf_after = int(fcf_after.replace(",", "").replace("$", ""))
            print(year, fcf_after, fcf_before)
            fcf_yoy.append(round_float_to_2dp(fcf_after - fcf_before)/float(abs(fcf_before))*100)
    #calculate future fcf growth
    print(fcf_yoy)
    for years_before in range(1,11):
        #Replace None with 0 for calculation
        fcf_calc = [0 if fcf_growth is None else fcf_growth for fcf_growth in fcf_yoy[years_before:years_before+10]]
        fcf_yoy.append(round_float_to_2dp(np.mean(fcf_calc) * dcf_discount_rate / 100))
    #Add perpetual growth rate
    perpetual_growth_rate = get_perpetual_growth_rate()
    fcf_yoy.append(perpetual_growth_rate)

    forecasted_fcf = get_forecasted_fcf(fcf_dict, fcf_yoy)

    #change to string and add '%'
    fcf_yoy = [None if fcf_growth is None else str(fcf_growth) + '%' for fcf_growth in fcf_yoy]

    return fcf_yoy, forecasted_fcf

def get_forecasted_fcf(fcf_dict, fcf_yoy):
    fcf_last_year = float(fcf_dict.get(str(datetime.datetime.now().year - 1)).replace(",", "").replace("$", ""))
    fcf_estimate = []
    fcf_estimate.append(fcf_last_year * (1 + fcf_yoy[10]/100))
    print(fcf_yoy)
    for index in range(11,21):
        fcf_estimate.append(round_float_to_2dp(fcf_estimate[index-11] * (1 + fcf_yoy[index]/100)))
    return fcf_estimate



def get_fcf_list_yoy(url, dcf_discount_rate):
    # fcf_dict = get_net_cash_flow_history(url)
    #DEBUG
    fcf_dict = {'2021': '$-3,860', '2020': '$-10,435', '2019': '$24,311', '2018': '$5,624', '2017': '$-195', '2016': '$-636', '2015': '$7,276', '2014': '$-415', '2013': '$3,513', '2012': '$931', '2011': '$-1,446', '2010': '$5,998', '2009': '$-6,612'}
    print("Macrotrends FCF Data: ", fcf_dict)
    fcf_list = []
    #Get past 10 years, if now 2022 means get 2012 - 2021
    for year in range(datetime.datetime.now().year-10, datetime.datetime.now().year):
        fcf = fcf_dict.get(str(year), None)
        fcf_list.append(fcf)

    #Get FCF YOY Growth
    fcf_yoy, forecasted_fcf = get_fcf_yoy_growth(fcf_dict, dcf_discount_rate)

    return fcf_list, fcf_yoy, forecasted_fcf

def round_float_to_2dp(floater):
    return float("{:.2f}".format(float(floater)))

def get_10_year_average_market_return():
    #TODO
    return 12.87

def get_cap_m_expected(company, risk_free_rate):
    _, beta = get_shares_outstanding_beta(company)
    round_float_to_2dp
    return round_float_to_2dp(risk_free_rate + beta * (get_10_year_average_market_return() - risk_free_rate))

def get_user_input(variable_type, default_value):
    variable = input('Enter ' + str(variable_type) + ' %, or leave blank for ' + str(default_value) + '%: ')
    if variable == '':
        variable = float(default_value)
    else:
        try:
            variable = round_float_to_2dp(variable)
        except:
            print("Please restart application and enter a valid " + str(variable_type))
    print("Input of " + str(variable_type) + " " + str(variable) + "%" + " accepted")
    return variable

def get_discount_rate():
    discount_rate = get_user_input('discount_rate', '50')
    return discount_rate

def get_perpetual_growth_rate():
    perpetual_growth_rate = get_user_input('perpetual_growth_rate', '5.0')
    return perpetual_growth_rate

def get_10_year_treasury_risk_free_rate():
    risk_free_rate = get_user_input('10-year-treasury-risk-free-rate', '1.6')
    return risk_free_rate

def get_shares_outstanding_beta(company):
    tick = Ticker(company)
    ticker = tick.key_stats[company]
    shares_outstanding = ticker['sharesOutstanding']
    beta = ticker['beta']
    return shares_outstanding, beta

def get_EBITDA(company):
    tick = Ticker(company)
    ticker = tick.financial_data[company]
    EBITDA = ticker['ebitda']
    return EBITDA

def get_price(company):
    tick = Ticker(company)
    ticker = tick.price[company]
    price = ticker['regularMarketPrice']
    return price

def get_company_financial_data(company):
    aapl = Ticker(company)
    types = ['TotalDebt', 'CashAndCashEquivalents', 'EBIT', 'EBITDA', 'PeRatio']
    aapl.get_financial_data(types, trailing=False)

def get_inputs():
    #Get input by typing or from a csv
    csv_input_option = input('Input companies via CSV?: (type only "yes" or "no")')
    if csv_input_option == 'yes':
        csv_dir = input('Paste full file path here: ')
        print("Entered directory: ", csv_dir)
        try:
            csv_list = pd.read_csv(csv_dir, header=None)
            companies_list = list(csv_list[0])
        except:
            print("File not found, please restart application")
    elif csv_input_option == 'no':
        companies_string = input('Type in companies stock ticker concatenanted by comma: ')
        companies_list = list(companies_string.split(","))
    else:
        print("Invalid input, please restart application")
        
    print("Companies to be calculated: ", companies_list)
    return companies_list

def change_list_to_concatanable_form(data_list, list_of_columns):
    return_dict = {}
    for i, col_name in enumerate(list_of_columns):
        return_dict[col_name] = data_list[i]
    return pd.DataFrame(return_dict, index=[0])

def construct_company_dcf(company):
    dcf_discount_rate = get_discount_rate()
    risk_free_rate = get_10_year_treasury_risk_free_rate()
    # url = get_macrotrends_correct_url(company)
    url = "TEST URL"
    number_of_columns = 23
    column_name_placeholder = [(i * '.') for i in range(1,number_of_columns - 2 + 1)]
    list_of_columns = ['Stock', company] + column_name_placeholder

    df_main = pd.DataFrame(columns = list_of_columns)

    #All rows here follow the excel provided by @shaopinglim
    row_2 = change_list_to_concatanable_form(['Source', "Current Year", datetime.datetime.now().year] + [None for i in range(1,number_of_columns - 3 + 1)], list_of_columns)
    row_3 = change_list_to_concatanable_form([None, 'Year'] + [year for year in range(datetime.datetime.now().year - 10, datetime.datetime.now().year + 10)] + ['Perpetual'], list_of_columns)
    fcf_list, fcf_yoy, forecasted_fcf = get_fcf_list_yoy(url, dcf_discount_rate)
    row_4 = change_list_to_concatanable_form(['Cash Flow Statement/macrotrends.net', 'Free Cash Flow, FCF (million USD)'] + fcf_list + [None for i in range(11)], list_of_columns)
    row_5 = change_list_to_concatanable_form(['Actual/Estimate', 'FCF y-o-y growth (%)'] + fcf_yoy, list_of_columns)
    row_6 = change_list_to_concatanable_form(['Estimate', 'Forecasted FCF (million USD)'] + [None for i in range(11)] + forecasted_fcf, list_of_columns)
    cap_m_expected = get_cap_m_expected(company, risk_free_rate)
    row_7 = change_list_to_concatanable_form(['Required Return for us', 'Discount Rate (%)'] + [None for i in range(10)] + [cap_m_expected for i in range(11)], list_of_columns)

    df_main = pd.concat([df_main,row_2, row_3, row_4, row_5, row_6, row_7], ignore_index=True)

    print(df_main)
    df_main.to_csv("Test.csv")
    return df_main        



if __name__ == "__main__":
    # stocks = get_inputs()
    stocks = ['AAPL']
    dcf_list = []
    for company in stocks:
        dcf_list.append(construct_company_dcf(company))
        break
    time.sleep(100)