class OrderBookCalculator:
    def __init__(self, exchange, ticker1, ticker2):
        self.exchange = exchange
        self.ticker1 = ticker1
        self.ticker2 = ticker2
        self.ticker1_orderbook = self.exchange.fetch_order_book(ticker1, 100)
        self.ticker2_orderbook = self.exchange.fetch_order_book(ticker2, 100)

    def calculate_average_price(self, array, amount_to_buy):
        sum_so_far = 0.0
        unit_bought = 0.0
        for i in array:
            price = i[0]
            dollar_amount = i[1]
            unit = dollar_amount / price
            unit_bought += unit
            sum_so_far += dollar_amount
            if sum_so_far > amount_to_buy:
                break
        average_price = sum_so_far / unit_bought

        return average_price

    def get_impact_fee_by_amount(self, ticker, amount_to_buy):
        # orderbook = self.exchange.fetch_order_book(coin, 100)
        if ticker == self.ticker1:
            orderbook = self.ticker1_orderbook
        elif ticker == self.ticker2:
            orderbook = self.ticker2_orderbook
        else:
            raise Exception('ticker does not match neither ticker in orderbook class')
        bids = orderbook['bids']
        asks = orderbook['asks']
        average_bids = self.calculate_average_price(bids, amount_to_buy)
        average_asks = self.calculate_average_price(asks, amount_to_buy)

        bid_ask_spread = asks[0][0] - bids[0][0]
        medium = asks[0][0] - bid_ask_spread / 2

        bids_quote_difference = abs(medium - average_bids) / medium
        asks_quote_difference = abs(medium - average_asks) / medium

        return {'bids':round(bids_quote_difference, 6), 'asks':round(asks_quote_difference, 6)}

    def get_impact_fee_by_bid_ask(self, ticker):
        if ticker == self.ticker1:
            orderbook = self.ticker1_orderbook
        elif ticker == self.ticker2:
            orderbook = self.ticker2_orderbook
        else:
            raise Exception('ticker does not match neither ticker in orderbook class')
        bid_ask_spread = orderbook['asks'][0][0] - orderbook['bids'][0][0]
        medium = orderbook['asks'][0][0] - bid_ask_spread / 2
        bids_quote_difference = abs(medium - orderbook['bids'][0][0]) / medium
        asks_quote_difference = abs(medium - orderbook['asks'][0][0]) / medium
        return round(bids_quote_difference, 6), round(asks_quote_difference, 6)

