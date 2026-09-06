"""
Mock MT5 Module for Testing Without MetaTrader5 Installation
Wisdom Lord Raphael - Core Analytical Engine & Financial Risk Guard
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import random


logger = logging.getLogger(__name__)


class MockMT5:
    """Mock MT5 implementation for testing without actual MT5 installation"""
    
    def __init__(self):
        self.is_initialized = False
        self.is_logged_in = False
        self.mock_account = {
            'login': 12345678,
            'balance': 570000.0,   # IDR
            'equity': 570000.0,    # IDR
            'margin': 0.0,
            'margin_free': 570000.0,
            'margin_level': 0.0,
            'currency': 'IDR',
            'profit': 0.0,
            'server': 'HFM-Demo-Mock'
        }
        
    def initialize(self) -> bool:
        """Mock initialize - always returns True"""
        self.is_initialized = True
        logger.info("🧪 Mock MT5 initialized successfully")
        return True
    
    def login(self, login: int, password: str, server: str) -> bool:
        """Mock login - always returns True"""
        self.is_logged_in = True
        self.mock_account['login'] = login
        self.mock_account['server'] = server
        logger.info(f"🧪 Mock MT5 logged in as {login} on {server}")
        return True
    
    def shutdown(self) -> None:
        """Mock shutdown"""
        self.is_initialized = False
        self.is_logged_in = False
        logger.info("🧪 Mock MT5 shutdown")
    
    def account_info(self) -> Optional[Dict[str, Any]]:
        """Mock account info"""
        if not self.is_initialized:
            return None
        
        # Add some random variation to equity
        self.mock_account['equity'] = self.mock_account['balance'] + random.uniform(-1000, 1000)
        self.mock_account['profit'] = self.mock_account['equity'] - self.mock_account['balance']
        
        return type('AccountInfo', (), self.mock_account)()
    
    @staticmethod
    def _get_base_price(symbol: str) -> tuple[float, int, float]:
        """Returns (base_price, digits, point) for a given symbol."""
        s = symbol.upper()
        if 'XAU' in s or 'GOLD' in s:
            return 2850.00, 2, 0.01
        if 'XAG' in s or 'SILVER' in s:
            return 32.00, 3, 0.001
        if 'BTC' in s:
            return 90000.00, 2, 0.01
        if 'ETH' in s:
            return 3300.00, 2, 0.01
        if 'JPY' in s:
            if 'GBP' in s:
                return 190.50, 3, 0.001
            if 'EUR' in s:
                return 162.00, 3, 0.001
            return 152.50, 3, 0.001
        if 'US30' in s:
            return 43000.00, 1, 0.1
        if 'NAS100' in s or 'USTEC' in s:
            return 20500.00, 1, 0.1
        if 'JPN225' in s:
            return 38500.00, 0, 1.0
        if 'GER40' in s:
            return 19200.00, 1, 0.1
        if 'GBP' in s:
            return 1.2950, 5, 0.00001
        if 'AUD' in s:
            return 0.6550, 5, 0.00001
        if 'NZD' in s:
            return 0.5850, 5, 0.00001
        if 'CAD' in s:
            return 1.3950, 5, 0.00001
        if 'CHF' in s:
            return 0.8850, 5, 0.00001
        return 1.0850, 5, 0.00001

    def symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Mock symbol info"""
        if not self.is_initialized:
            return None
        
        base_price, digits, point = self._get_base_price(symbol)
        spread_val = point * 15
        
        return type('SymbolInfo', (), {
            'name': symbol,
            'bid': round(base_price - (spread_val / 2), digits),
            'ask': round(base_price + (spread_val / 2), digits),
            'spread': round(spread_val, digits),
            'point': point,
            'trade_tick_size': point,
            'trade_tick_value': 1.0,
            'volume_min': 0.01,
            'volume_max': 100.0,
            'volume_step': 0.01,
            'digits': digits
        })()
    
    def symbol_info_tick(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Mock symbol tick info"""
        if not self.is_initialized:
            return None
        
        symbol_info = self.symbol_info(symbol)
        if symbol_info:
            return type('Tick', (), {
                'bid': symbol_info.bid,
                'ask': symbol_info.ask,
                'time': datetime.now().timestamp()
            })()
        return None
    
    def copy_rates_from_pos(self, symbol: str, timeframe: int, start_pos: int, count: int) -> Optional[List]:
        """Mock rates data - generates realistic OHLC data"""
        if not self.is_initialized:
            return None
        
        import pandas as pd
        import numpy as np
        
        base_price, digits, point = self._get_base_price(symbol)
        dates = pd.date_range(end=datetime.now(), periods=count, freq='h')
        
        # Generate random walk for prices
        np.random.seed(42)
        returns = np.random.normal(0.0001, 0.001, count)
        prices = base_price * (1 + returns).cumprod()
        
        # Create OHLC data
        data = []
        for i in range(count):
            high = prices[i] * (1 + random.uniform(0, 0.001))
            low = prices[i] * (1 - random.uniform(0, 0.001))
            open_price = prices[i] if i == 0 else prices[i-1]
            close = prices[i]
            
            data.append({
                'time': int(dates[i].timestamp()),
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'tick_volume': random.randint(100, 1000),
                'spread': random.randint(1, 20),
                'real_volume': random.randint(1000, 10000)
            })
        
        return data
    
    def positions_get(self) -> Optional[List]:
        """Mock positions - returns empty list"""
        if not self.is_initialized:
            return None
        return []
    
    def last_error(self) -> tuple:
        """Mock last error"""
        return (0, 'No error')


# Create module-level functions that mimic MetaTrader5 module interface
_mt5_instance = MockMT5()
_mt5_instance.initialize()

def initialize() -> bool:
    return _mt5_instance.initialize()

def login(login: int, password: str, server: str) -> bool:
    return _mt5_instance.login(login, password, server)

def shutdown() -> None:
    _mt5_instance.shutdown()

def account_info() -> Optional[Dict[str, Any]]:
    return _mt5_instance.account_info()

def symbol_info(symbol: str) -> Optional[Dict[str, Any]]:
    return _mt5_instance.symbol_info(symbol)

def symbol_info_tick(symbol: str) -> Optional[Dict[str, Any]]:
    return _mt5_instance.symbol_info_tick(symbol)

def copy_rates_from_pos(symbol: str, timeframe: int, start_pos: int, count: int) -> Optional[List]:
    return _mt5_instance.copy_rates_from_pos(symbol, timeframe, start_pos, count)

def positions_get() -> Optional[List]:
    return _mt5_instance.positions_get()

def last_error() -> tuple:
    return _mt5_instance.last_error()

# Timeframe constants (matching MT5)
TIMEFRAME_M1  = 1
TIMEFRAME_M5  = 5
TIMEFRAME_M15 = 15
TIMEFRAME_M30 = 30
TIMEFRAME_H1  = 60
TIMEFRAME_H2  = 120
TIMEFRAME_H3  = 180
TIMEFRAME_H4  = 240
TIMEFRAME_H6  = 360
TIMEFRAME_H8  = 480
TIMEFRAME_H12 = 720
TIMEFRAME_D1  = 1440
TIMEFRAME_W1  = 10080
TIMEFRAME_MN1 = 43200