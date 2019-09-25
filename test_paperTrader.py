import unittest
from trader import PaperTrader
import ccxt

class TestPaperTrader(unittest.TestCase):

    def test_upper(self):
        pt = PaperTrader(ccxt.bitfinex(), 100, 'ETH/USD', 'EOS/USD', '1h')
        pt.preload_data()


if __name__ == '__main__':
    unittest.main()
