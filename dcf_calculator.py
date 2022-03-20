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

def get_fcf_yoy_growth(fcf_dict, dcf_discount_rate, perpetual_growth_rate):
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
            try:
                fcf_before = int(fcf_before.replace(",", "").replace("$", ""))
                fcf_after = int(fcf_after.replace(",", "").replace("$", ""))
                fcf_yoy.append(round_float_to_2dp((fcf_after - fcf_before)/float(abs(fcf_before))*100))
            except:
                fcf_yoy.append(None)
    #calculate future fcf growth
    for years_before in range(1,11):
        #Replace None with 0 for calculation
        fcf_calc = [np.nan if fcf_growth is None else fcf_growth for fcf_growth in fcf_yoy[years_before:years_before+10]]
        fcf_yoy.append(round_float_to_2dp(np.nanmean(fcf_calc) * dcf_discount_rate / 100))
    #Add perpetual growth rate
    fcf_yoy.append(perpetual_growth_rate)

    forecasted_fcf = get_forecasted_fcf(fcf_dict, fcf_yoy)

    #change to string and add '%'
    fcf_yoy = [None if fcf_growth is None else str(fcf_growth) + '%' for fcf_growth in fcf_yoy]

    return fcf_yoy, forecasted_fcf

def get_forecasted_fcf(fcf_dict, fcf_yoy):
    for year in reversed(range(datetime.datetime.now().year-10, datetime.datetime.now().year)):
        fcf_last_year_pre = fcf_dict.get(str(datetime.datetime.now().year - 1), None)
        if fcf_last_year_pre != None:
            break
    if fcf_last_year_pre == None:
        print("WARNING: NO FCF FOR PAST ALL YEARS")
        fcf_last_year_pre = str(0)
    fcf_last_year = float(fcf_last_year_pre.replace(",", "").replace("$", ""))
    fcf_estimate = []
    fcf_estimate.append(fcf_last_year * (1 + fcf_yoy[10]/100))
    # print(fcf_yoy)
    for index in range(11,21):
        fcf_estimate.append(round_float_to_2dp(fcf_estimate[index-11] * (1 + fcf_yoy[index]/100)))
    return fcf_estimate



def get_fcf_list_yoy(url, dcf_discount_rate, perpetual_growth_rate):
    fcf_dict = get_net_cash_flow_history(url)
    #DEBUG
    # fcf_dict = {'2021': '$-3,860', '2020': '$-10,435', '2019': '$24,311', '2018': '$5,624', '2017': '$-195', '2016': '$-636', '2015': '$7,276', '2014': '$-415', '2013': '$3,513', '2012': '$931', '2011': '$-1,446', '2010': '$5,998', '2009': '$-6,612'}
    print("Macrotrends FCF Data: ", fcf_dict)
    fcf_list = []
    #Get past 10 years, if now 2022 means get 2012 - 2021
    for year in range(datetime.datetime.now().year-10, datetime.datetime.now().year):
        fcf = fcf_dict.get(str(year), None)
        fcf_list.append(fcf)

    #Get FCF YOY Growth
    fcf_yoy, forecasted_fcf = get_fcf_yoy_growth(fcf_dict, dcf_discount_rate, perpetual_growth_rate)

    return fcf_list, fcf_yoy, forecasted_fcf

def round_float_to_2dp(floater):
    return float("{:.2f}".format(float(floater)))

def get_10_year_average_market_return():
    #TODO
    return 12.87

def get_cap_m_expected(company, risk_free_rate):
    _, beta, _ = get_shares_outstanding_beta_ev(company)
    round_float_to_2dp
    return round_float_to_2dp(risk_free_rate + beta * (get_10_year_average_market_return() - risk_free_rate))

def get_user_input(variable_type, default_value):
    variable = input('Enter ' + str(variable_type) + ', or leave blank for ' + str(default_value) + ': ')
    if variable == '':
        variable = float(default_value)
    else:
        try:
            variable = round_float_to_2dp(variable)
        except:
            print("Please restart application and enter a valid " + str(variable_type))
    print("Input of " + str(variable_type) + " " + str(variable) + " accepted\n")
    return variable

def get_minority_interest():
    minority_interest = get_user_input('minority_interest', '0')
    return minority_interest

def get_discount_rate():
    discount_rate = get_user_input('discount_rate %', '50')
    return discount_rate

def get_perpetual_growth_rate():
    perpetual_growth_rate = get_user_input('perpetual_growth_rate %', '5.0')
    return perpetual_growth_rate

def get_10_year_treasury_risk_free_rate():
    risk_free_rate = get_user_input('10-year-treasury-risk-free-rate %', '1.6')
    return risk_free_rate

def get_shares_outstanding_beta_ev(company):
    tick = Ticker(company)
    ticker = tick.key_stats[company]
    shares_outstanding = ticker['sharesOutstanding']
    beta = ticker['beta']
    enterprise_val = ticker['enterpriseValue']
    return shares_outstanding, beta, enterprise_val

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
    tick = Ticker(company)
    ticker = tick.financial_data[company]
    debt = ticker['totalDebt']
    cash = ticker['totalCash']
    EBITDA = ticker['ebitda']
    return debt, cash, EBITDA

# def get_company_financial_data(company):
#     tick = Ticker(company)
#     types = ['TotalDebt', 'CashAndCashEquivalents', 'EBITDA']
#     data = tick.get_financial_data(types, trailing=False)
#     try:
#         row = data.iloc[len(data)-1]
#         debt = row['TotalDebt']/1_000_000
#         cash = row['CashAndCashEquivalents']/1_000_000
#         cash = row['CashAndCashEquivalents']/1_000_000
#     except:
#         debt = None
#         cash = None
#         ebitda = None
        
#     return debt, cash, ebitda

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

def get_discounted_fcf(forecasted_fcf, cap_m_expected, perpetual_growth_rate):
    discounted_fcf = []
    for index, forecasted in enumerate(forecasted_fcf[:-1]):
        discounted_fcf.append(round_float_to_2dp(forecasted/((1+cap_m_expected/100)**index)))
    discounted_fcf.append(round_float_to_2dp(forecasted_fcf[-1]*(1+perpetual_growth_rate/100)/(cap_m_expected/100-perpetual_growth_rate/100)/((1+cap_m_expected/100)**index)))
    return discounted_fcf

def get_total_present_fcf(discounted_fcf):
    return(round_float_to_2dp(sum(discounted_fcf)))

def get_derived_shareholder_equity(total_present_fcf, minority_interest, debt, cash):
    if minority_interest == None:
        minority_interest = 0
    return round_float_to_2dp(total_present_fcf - minority_interest - debt + cash)

def construct_company_dcf(company):
    dcf_discount_rate = get_discount_rate()
    risk_free_rate = get_10_year_treasury_risk_free_rate()
    perpetual_growth_rate = get_perpetual_growth_rate()
    minority_interest = get_minority_interest()
    url = get_macrotrends_correct_url(company)
    # url = "TEST URL"
    number_of_columns = 23
    column_name_placeholder = [(i * ' ') for i in range(1,number_of_columns - 2 + 1)]
    list_of_columns = ['Stock', company] + column_name_placeholder

    df_main = pd.DataFrame(columns = list_of_columns)

    #All rows here follow the excel provided by @shaopinglim
    row_2 = change_list_to_concatanable_form(['Source', "Current Year", datetime.datetime.now().year] + [None for i in range(1,number_of_columns - 3 + 1)], list_of_columns)
    row_3 = change_list_to_concatanable_form([None, 'Year'] + [year for year in range(datetime.datetime.now().year - 10, datetime.datetime.now().year + 10)] + ['Perpetual'], list_of_columns)
    fcf_list, fcf_yoy, forecasted_fcf = get_fcf_list_yoy(url, dcf_discount_rate, perpetual_growth_rate)
    row_4 = change_list_to_concatanable_form(['Cash Flow Statement/macrotrends.net', 'Free Cash Flow, FCF (million USD)'] + fcf_list + [None for i in range(11)], list_of_columns)
    row_5 = change_list_to_concatanable_form(['Actual/Estimate', 'FCF y-o-y growth (%)'] + fcf_yoy, list_of_columns)
    row_6 = change_list_to_concatanable_form(['Estimate', 'Forecasted FCF (million USD)'] + [None for i in range(11)] + forecasted_fcf, list_of_columns)
    cap_m_expected = get_cap_m_expected(company, risk_free_rate)
    row_7 = change_list_to_concatanable_form(['Required Return for us', 'Discount Rate (%)'] + [None for i in range(10)] + [cap_m_expected for i in range(11)], list_of_columns)
    discounted_fcf = get_discounted_fcf(forecasted_fcf, cap_m_expected, perpetual_growth_rate)
    row_8 = change_list_to_concatanable_form([None, 'Discounted FCF (million USD)'] + [None for i in range(10)] + discounted_fcf, list_of_columns)
    total_present_fcf = get_total_present_fcf(discounted_fcf)
    row_9 = change_list_to_concatanable_form([None, 'Total Present FCF (million USD)'] + [None for i in range(10)] + [total_present_fcf] + [None for i in range(10)], list_of_columns)
    row_10 = change_list_to_concatanable_form([None, 'Minority interest (million USD)'] + [None for i in range(10)] + [minority_interest] + [None for i in range(10)], list_of_columns)
    debt, cash, ebitda = get_company_financial_data(company)
    row_11 = change_list_to_concatanable_form([None, 'Total Debt (million USD)'] + [None for i in range(10)] + [debt] + [None for i in range(10)], list_of_columns)
    row_12 = change_list_to_concatanable_form([None, 'Cash and Cash Equivalent (million USD)'] + [None for i in range(10)] + [cash] + [None for i in range(10)], list_of_columns)
    derived_shareholder_equity = get_derived_shareholder_equity(total_present_fcf, minority_interest, debt, cash)
    row_13 = change_list_to_concatanable_form(['Balance Sheet/macrotrends.net', 'Derived Shareholder Equity (million USD)'] + [None for i in range(10)] + [derived_shareholder_equity] + [None for i in range(10)], list_of_columns)
    row_14 = change_list_to_concatanable_form([None for i in range(23)], list_of_columns)
    shares_outstanding, beta, ev = get_shares_outstanding_beta_ev(company)
    shares_outstanding = round_float_to_2dp(shares_outstanding/1_000_000)
    row_15 = change_list_to_concatanable_form(['Financial Statement/macrotrends.net', 'Number of outstanding shares (million)'] + [None for i in range(10)] + [shares_outstanding] + [None for i in range(10)], list_of_columns)
    value_of_share = round_float_to_2dp(derived_shareholder_equity/shares_outstanding)
    row_16 = change_list_to_concatanable_form([None, 'Value/share (USD)'] + [None for i in range(10)] + [value_of_share] + [None for i in range(10)], list_of_columns)
    price = get_price(company)
    row_17 = change_list_to_concatanable_form(['Google/Broker', 'Current price/share (USD)'] + [None for i in range(10)] + [price] + [None for i in range(10)], list_of_columns)
    premium = round_float_to_2dp((price/value_of_share - 1) * 100)
    row_18 = change_list_to_concatanable_form([None, 'Premium (+ve)/Discount (-ve) (%)'] + [None for i in range(10)] + [str(premium) + '%'] + [None for i in range(10)], list_of_columns)
    row_19 = change_list_to_concatanable_form([None for i in range(23)], list_of_columns)
    row_20 = change_list_to_concatanable_form(['macrotrends.net', 'S&P 500 year close (USD)'] + ['TODO' for i in range(10)] + [None for i in range(11)], list_of_columns)
    row_21 = change_list_to_concatanable_form([None, 'Market Return (%)', None] + ['TODO' for i in range(9)] + [None for i in range(11)], list_of_columns)
    row_22 = change_list_to_concatanable_form([None, '10 - year average Market Return (%)'] + [None for i in range(10)] + ['12.87'] +[None for i in range(10)], list_of_columns)
    row_23 = change_list_to_concatanable_form(['Yahoo Finance', 'Stock Beta (5Y monthly)'] + [None for i in range(10)] + [beta] +[None for i in range(10)], list_of_columns)
    row_24 = change_list_to_concatanable_form(['10-year US treasury', 'Risk-Free Rate (%)'] + [None for i in range(10)] + [risk_free_rate] +[None for i in range(10)], list_of_columns)
    row_25 = change_list_to_concatanable_form(['CAPM model', 'Expected Return (%)'] + [None for i in range(10)] + [cap_m_expected] +[None for i in range(10)], list_of_columns)
    row_26 = change_list_to_concatanable_form([None for i in range(23)], list_of_columns)
    enterprise_value = price * shares_outstanding - cash + debt
    row_27 = change_list_to_concatanable_form([None, 'Enterprise Value (million USD)'] + [None for i in range(10)] + [cap_m_expected] +[None for i in range(10)], list_of_columns)
    row_28 = change_list_to_concatanable_form([None, '12 - month EBITDA (million USD)'] + [None for i in range(10)] + [ebitda] +[None for i in range(10)], list_of_columns)
    row_29 = change_list_to_concatanable_form([None, 'EV/EBITDA'] + [None for i in range(10)] + [round_float_to_2dp(ev/ebitda)] +[None for i in range(10)], list_of_columns)

    df_main = pd.concat([df_main,row_2, row_3, row_4, row_5, row_6, row_7, row_8, row_9, row_10, row_11, row_12, row_13, row_14, row_15, 
                            row_16, row_17, row_18, row_19, row_20, row_21, row_22, row_23, row_24, row_25, row_26, row_27, row_28, row_29], ignore_index=True)

    print(df_main)
    return df_main        



if __name__ == "__main__":
    try:
        stocks = get_inputs()
        dcf_list = []
        for company in stocks:
            driver = webdriver.Chrome(browser_driver, options=options)
            print("WORKING ON ", company)
            dcf_list.append(construct_company_dcf(company))
            driver.close()
            driver.quit()

        #save the file
        today = str(datetime.datetime.now())
        today = today.replace(":", ".")

        #Export to excel
        result_save_folder = input("Enter result save folder, or leave blank for same location: ")
        if result_save_folder == '':
            filename = today + '.xlsx'
        else:
            filename = result_save_folder+'//'+today+".xlsx"
        
        # Create a Pandas Excel writer using XlsxWriter as the engine.
        writer = pd.ExcelWriter(filename, engine='xlsxwriter')

        for index, result in enumerate(dcf_list):
            result.to_excel(writer, sheet_name=stocks[index])
        writer.save()
        print("Results saved to: ", filename)
        
    except:
        print(traceback.format_exc())
        print("If you don't understand the error please show it to the developer")
        time.sleep(100)