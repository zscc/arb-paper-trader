# Kalman Filter Statistical Arbitrage Paper Trader

This is a paper trader system for a statistical arbitrage method. The method uses Kalman Filter, a state space model that is used for producing estimates from data that has noise. Statistical arbitrage is a quantitative investing method that seek to find two securities with pre-existing correlation/cointegration relationship and invest in market neutral long-short pair trading strategy when the two securities deviate too far out from each other, in the hopes of them converging, resulting in profits. In this case the Kalman Filter, instead of the tradition OLS, is used to smooth out noise in the securities' movements to not get confused by temporary price deviation.

