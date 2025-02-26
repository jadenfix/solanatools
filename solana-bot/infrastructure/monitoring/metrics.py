from prometheus_client import start_http_server, Counter, Gauge

class TradingMetrics:
    def __init__(self):
        self.trades_executed = Counter('trades_total', 'Total executed trades')
        self.latency = Gauge('trade_latency', 'Trade execution latency')
        self.slippage = Gauge('trade_slippage', 'Execution slippage')
        
    def start_exporter(self, port=9100):
        start_http_server(port)
