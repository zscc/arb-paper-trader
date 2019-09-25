import datetime
import pprint
import requests
import pandas as pd
import ccxt
import kalman_filter as kf
import orderbook_calculator as calculator
import time


class PaperTrader:

    def __init__(self, exchange, impact_amount, ticker1, ticker2, frequency):
        self.exchange = exchange
        self.impact_amount = impact_amount
        self.ticker1 = ticker1
        self.ticker2 = ticker2
        margin_array = ticker1.split("/")
        self.margin = "f" + margin_array[1]
        self.frequency = frequency
        self.frequency_in_seconds = self.get_frequency_in_seconds(frequency)
        self.oc = calculator.OrderBookCalculator(self.exchange, ticker1, ticker2)

    def get_frequency_in_seconds(self, frequency):
        switcher = {
            '6h': 21600.0,
            '3h': 10800.0,
            '1h': 3600.0,
            '30m': 1800.0}
        return switcher.get(frequency, 'invalid')

    def check_status(self):
        if self.exchange.fetch_status()['status'] == 'ok':
            return True
        return False

    def preload_data(self):
        # first calculate in seconds
        from_timestamp = ( int(time.time()) - 60*60*24*60 ) * 1000 # times it by 1000 converts to ms
        print('in preload_data:', pd.to_datetime(from_timestamp, unit='ms'))

        ticker1_data = pd.DataFrame(
            self.exchange.fetchOHLCV(symbol=self.ticker1, timeframe=self.frequency, limit=1440, since=from_timestamp))[:-1]
        # [:-1] to delete last entry as loop will request most recent one at the start
        ticker2_data = pd.DataFrame(
            self.exchange.fetchOHLCV(symbol=self.ticker2, timeframe=self.frequency, limit=1440, since=from_timestamp))[:-1]
        file_name = 'bitfinex/database/' + self.ticker1.split('/')[0] + \
                    self.ticker2.split('/')[0] + self.frequency + '.csv'

        pd.DataFrame({'timestamp':pd.to_datetime(ticker1_data[0], unit='ms'),
                      self.ticker1: ticker1_data[4],
                      self.ticker2: ticker2_data[4]}).to_csv(file_name, index=False)

    def get_prices_by_tickers(self, ticker1, ticker2):
        ticker1_average = self.exchange.fetch_ticker(ticker1)['average']
        ticker2_average = self.exchange.fetch_ticker(ticker2)['average']
        print(ticker1, ticker1_average)
        print(ticker2, ticker2_average)
        return ticker1_average, ticker2_average

    def send_to_database(self, ticker1, ticker2, ticker1_data, ticker2_data):
        old_data_file_name = 'bitfinex/database/' + self.ticker1.split('/')[0] + \
                             self.ticker2.split('/')[0] + self.frequency + '.csv'
        try:
            old_data = pd.read_csv(old_data_file_name, index_col=0)
        except Exception as e:
            print('read_csv does not work. file not created yet possibly')
            old_data = pd.DataFrame()
        now = pd.datetime.utcnow()
        d = {'timestamp': now, ticker1: [ticker1_data], ticker2: [ticker2_data]}
        new_data = pd.DataFrame(data=d).set_index('timestamp')
        old_data = old_data.append(new_data, sort=False)
        old_data.to_csv(old_data_file_name)

    def calculate(self, x, y):
        state_means = kf.kalman_filter_regression(kf.kalman_filter_average(x),
                                                  kf.kalman_filter_average(y))
        return state_means

    def get_impact_fee_by_amount(self, ticker, amount):
        return self.oc.get_impact_fee_by_amount(ticker, self.impact_amount)

    def get_impact_fee_by_bid_ask(self, ticker):
        return self.oc.get_impact_fee_by_bid_ask(ticker)

    def get_margin_fee(self):
        url = 'https://api-pub.bitfinex.com/v2/ticker/' + self.margin
        r = requests.get(url)
        data = r.json()
        result = pd.DataFrame(data)[0][0]
        return result

    def get_commission(self):
        return self.exchange.describe()['fees']['trading']['taker']

    def perform_kalman_filtering(self, ticker1, ticker2, calculation_sheet):
        state_means = self.calculate(calculation_sheet[ticker1], calculation_sheet[ticker2])
        calculation_sheet['hr'] = state_means[:, 0]
        calculation_sheet['error'] = state_means[:, 1]
        calculation_sheet['spread'] = calculation_sheet[ticker2] - calculation_sheet[ticker1] * \
                                      calculation_sheet.hr - calculation_sheet.error

        spread_mean = calculation_sheet.spread.rolling(window=720).mean()
        print(spread_mean)
        spread_std = calculation_sheet.spread.rolling(window=720).std()
        calculation_sheet['z_score'] = (calculation_sheet.spread - spread_mean) \
                                       / spread_std
        print(calculation_sheet)
        try:
            prev_z_score = calculation_sheet['z_score'].iloc[-2]
            prev_spread = calculation_sheet['spread'].iloc[-2]
        except IndexError as e:
            print('prev_z_score/spread (iloc[-2]) out of bound. Using 0 instead')
            prev_z_score = 0
            prev_spread = 0
        try:
            current_z_score = calculation_sheet['z_score'].iloc[-1]
            current_spread = calculation_sheet['spread'].iloc[-1]
        except Exception as e:
            print('current_z_score/spread (iloc[-1]) out of bound. Using 0 instead')
            current_z_score = 0
            current_spread = 0

        print (current_z_score)
        hr = state_means[:, 0][-1]
        return prev_z_score, current_z_score, prev_spread, current_spread, hr 

    def process_data(self, ticker1, ticker2, entry_z_score, exit_z_score):
        data_file_name = 'bitfinex/database/' + self.ticker1.split('/')[0] + \
                             self.ticker2.split('/')[0] + self.frequency + '.csv'
        calculation_sheet = pd.read_csv(data_file_name)

        current_data = calculation_sheet.iloc[-1].to_dict()
        # here current_data consist of time, price of ticker1, and price of ticker2

        calculation_sheet.set_index('timestamp', inplace=True)
        
        prev_z_score, current_z_score, prev_spread, current_spread, hr = \
            self.perform_kalman_filtering(ticker1, ticker2, calculation_sheet)
        current_data['z_score'] = current_z_score
        print(current_z_score)
        current_data['hr'] = hr
        
        prev_num_unit = 0
        prev_cumul_return = 1

        result_file_name = 'bitfinex/result/' + self.ticker1.split('/')[0] + \
                             self.ticker2.split('/')[0] + self.frequency + '.csv'
        try:
            prev_data = pd.read_csv(result_file_name, index_col=0)
            if 'num_units' in prev_data.columns:
                prev_num_unit = prev_data['num_units'].iloc[-1]
            if 'cumul_return' in prev_data.columns:
                prev_cumul_return = prev_data['cumul_return'].iloc[-1]
        except Exception as e:
            print('no file/content yet' + str(e))
            
        x = calculation_sheet.loc[:,ticker1][-1]
        y = calculation_sheet.loc[:,ticker2][-1]

        long_entry = False
        long_exit = False
        short_entry = False
        short_exit = False
        num_of_unit_long = 0
        num_of_unit_short = 0
        commission = self.get_commission()
        actual_commission = 0
        impact_fee = 0
        margin_fee = 0

        if (current_z_score < - entry_z_score) & (prev_z_score > - entry_z_score):
            long_entry = True
            num_of_unit_long = 1

        if (current_z_score > - exit_z_score) & (prev_z_score < - exit_z_score):
            long_exit = True
            num_of_unit_long = 0

        if (current_z_score > entry_z_score) & (prev_z_score < entry_z_score):
            short_entry = True
            num_of_unit_short = -1

        if (current_z_score < exit_z_score) & (prev_z_score > exit_z_score):
            short_exit = True
            num_of_unit_short = 0

        current_data['num_of_unit_long'] = num_of_unit_long
        current_data['num_of_unit_short'] = num_of_unit_short
        num_units = num_of_unit_long + num_of_unit_short

        if num_units == 1:
            # x_return is calculated by x_curr_price - x_init_price
            # x_portion is the percentage of x in the portfolio and is calculated by x * init_hr

            curr_return = -x_return * x_portion + y_return * y_portion


        current_data['num_units'] = num_units

        total_invested = x * abs(hr) + y
        current_data['total_invested'] = total_invested

        spread_pct_change = (current_spread - prev_spread) / total_invested

        current_data['spread_pct_change'] = spread_pct_change

        if (short_entry and long_exit) or (long_entry and short_exit):
            actual_commission = commission * 4
            impact_fee = self.get_impact_fee_by_amount(ticker1, self.impact_amount)['bids'] \
                         + self.get_impact_fee_by_amount(ticker1, self.impact_amount)['asks'] \
                         + self.get_impact_fee_by_amount(ticker2, self.impact_amount)['asks'] \
                         + self.get_impact_fee_by_amount(ticker2, self.impact_amount)['bids']
        elif long_entry or (short_exit and abs(prev_num_unit)):
            actual_commission = commission * 2
            impact_fee = self.get_impact_fee_by_amount(ticker1, self.impact_amount)['bids'] \
                         + self.get_impact_fee_by_amount(ticker2, self.impact_amount)['asks']
        elif short_entry or (long_exit and abs(prev_num_unit)):
            actual_commission = commission * 2
            impact_fee = self.get_impact_fee_by_amount(ticker1, self.impact_amount)['asks'] \
                         + self.get_impact_fee_by_amount(ticker2, self.impact_amount)['bids']

        current_data['actual_commission'] = actual_commission
        current_data['impact fee'] = impact_fee

        if prev_num_unit == -1:
            margin_fee = x * abs(hr) * (3600 / 86400.0) * self.get_margin_fee()
        elif prev_num_unit:
            margin_fee = y * (3600 / 86400.0) * self.get_margin_fee()

        current_data['margin_fee'] = margin_fee
        current_data['curr_return'] = spread_pct_change * prev_num_unit - actual_commission - margin_fee - impact_fee
        current_data['cumul_return'] = prev_cumul_return * (1 + current_data['curr_return'])

        current_pd = pd.Series(current_data).to_frame().T

        try:
            refreshed_data = prev_data.append(current_pd, sort=False)
        except Exception as e:
            print(e)
            refreshed_data = current_pd

        refreshed_data.to_csv(result_file_name)
        return current_data

    def main_loop(self):
        starttime = time.time()
        print('Started at:', datetime.datetime.now())
        self.preload_data()

        while True:
            ticker1_average, ticker2_average = self.get_prices_by_tickers(self.ticker1, self.ticker2)
            self.send_to_database(self.ticker1, self.ticker2, ticker1_average, ticker2_average)
            self.process_data(self.ticker1, self.ticker2, 2, 0)
            # time.sleep(self.frequency_in_seconds - ((time.time() - starttime) % self.frequency_in_seconds))
            time.sleep(10.0 - ((time.time() - starttime) % 10.0))


def main():
    
    bitfinex = ccxt.bitfinex()

    # pair1 = input('First pair: ')
    # pair2 = input('Second pair: ')
    # amount_to_invest = input('Amount to invest: ')
    # frequency = input('Frequency: ')
    pair1 = 'EOS/USD'
    pair2 = 'LTC/USD'
    amount_to_invest = 1000
    frequency = '1h'

    pt = PaperTrader(bitfinex, amount_to_invest, pair1, pair2, frequency)
    pt.main_loop()


main()

