"""
MT5 Connector Module for Raphael AI Bot
Wisdom Lord Raphael - Core Analytical Engine & Financial Risk Guard
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from config import Config
from mt5_module.mt5_loader import get_mt5_implementation

from utils.retry_queue import with_retry


logger = logging.getLogger(__name__)


class MT5Connector:
    """Connector for MetaTrader 5 terminal with retry logic"""
    
    def __init__(self, config: Config):
        """Initialize MT5 connector with configuration"""
        self.config = config
        
        # Get MT5 implementation based on config
        global mt5, MT5_IMPLEMENTATION, MT5_AVAILABLE
        mt5, MT5_IMPLEMENTATION, MT5_AVAILABLE = get_mt5_implementation(config.use_mock_mt5)
        
        self.is_connected = False
        self.account_info: Optional[Dict[str, Any]] = None
        self.cache_timeout = 60  # Cache data for 60 seconds
        self._cache = {}
        self._cache_timestamps = {}
        
    @with_retry(max_attempts=3, base_delay=5, exceptions=(Exception,))
    def initialize(self) -> bool:
        """Initialize MT5 connection with retry logic"""
        try:
            # Initialize MT5 based on implementation
            if MT5_IMPLEMENTATION == "mt5-mac":
                # mt5-mac has different initialization
                if not mt5.initialize():
                    logger.error("❌ MT5 (mt5-mac) initialization failed")
                    return False
            else:
                # Standard MetaTrader5 or mock
                if not mt5.initialize():
                    error_code = mt5.last_error()
                    logger.error(f"❌ MT5 initialization failed: {error_code}")
                    return False
            
            # Login if credentials provided (for standard MT5)
            if self.config.mt5_login > 0 and MT5_IMPLEMENTATION != "mt5-mac":
                if not mt5.login(
                    self.config.mt5_login,
                    password=self.config.mt5_password,
                    server=self.config.mt5_server
                ):
                    error_code = mt5.last_error()
                    logger.error(f"❌ MT5 login failed: {error_code}")
                    mt5.shutdown()
                    return False
            
            self.is_connected = True
            logger.info(f"✅ MT5 connection established successfully using {MT5_IMPLEMENTATION}")
            
            # Get account info
            self.account_info = self._get_account_info()
            logger.info(f"👤 Account: {self.account_info.get('login', 'Unknown')}")
            logger.info(f"💰 Balance: Rp {self.account_info.get('balance', 0):,.2f}")
            logger.info(f"💎 Equity: Rp {self.account_info.get('equity', 0):,.2f}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error initializing MT5: {e}", exc_info=True)
            self.is_connected = False
            return False
    
    def shutdown(self):
        """Shutdown MT5 connection"""
        if self.is_connected:
            try:
                mt5.shutdown()
            except Exception as e:
                logger.warning(f"⚠️  Error during MT5 shutdown: {e}")
            self.is_connected = False
            logger.info("🔌 MT5 connection closed")
    
    def _get_account_info(self) -> Dict[str, Any]:
        """Get account information from MT5"""
        account_info = mt5.account_info()
        if account_info is None:
            logger.error("❌ Failed to get account info")
            return {}
        
        return {
            'login': account_info.login,
            'balance': account_info.balance,
            'equity': account_info.equity,
            'margin': account_info.margin,
            'margin_free': account_info.margin_free,
            'margin_level': account_info.margin_level,
            'currency': account_info.currency,
            'profit': account_info.profit,
            'server': account_info.server
        }
    
    @with_retry(max_attempts=3, base_delay=2, exceptions=(Exception,))
    def get_account_info(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get current account information with caching"""
        cache_key = 'account_info'
        
        if not force_refresh and self._is_cache_valid(cache_key):
            return self._cache[cache_key]
        
        try:
            account_info = self._get_account_info()
            self._cache[cache_key] = account_info
            self._cache_timestamps[cache_key] = datetime.now()
            return account_info
        except Exception as e:
            logger.error(f"❌ Error getting account info: {e}")
            return self._cache.get(cache_key, {})
    
    @with_retry(max_attempts=3, base_delay=2, exceptions=(Exception,))
    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get symbol information from MT5"""
        try:
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                logger.warning(f"⚠️  Symbol {symbol} not found")
                return None
            
            return {
                'symbol': symbol_info.name,
                'bid': symbol_info.bid,
                'ask': symbol_info.ask,
                'spread': symbol_info.spread,
                'point': symbol_info.point,
                'trade_tick_size': symbol_info.trade_tick_size,
                'trade_tick_value': symbol_info.trade_tick_value,
                'volume_min': symbol_info.volume_min,
                'volume_max': symbol_info.volume_max,
                'volume_step': symbol_info.volume_step,
                'digits': symbol_info.digits
            }
        except Exception as e:
            logger.error(f"❌ Error getting symbol info for {symbol}: {e}")
            return None
    
    @with_retry(max_attempts=3, base_delay=2, exceptions=(Exception,))
    def get_current_prices(self, symbol: str) -> Optional[Dict[str, float]]:
        """Get current bid/ask prices for a symbol"""
        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                logger.warning(f"⚠️  Could not get tick data for {symbol}")
                return None
            
            return {
                'bid': tick.bid,
                'ask': tick.ask,
                'spread': tick.ask - tick.bid,
                'time': datetime.fromtimestamp(tick.time)
            }
        except Exception as e:
            logger.error(f"❌ Error getting current prices for {symbol}: {e}")
            return None
    
    @with_retry(max_attempts=3, base_delay=2, exceptions=(Exception,))
    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions"""
        try:
            positions = mt5.positions_get()
            if positions is None:
                return []
            
            position_list = []
            for position in positions:
                position_list.append({
                    'ticket': position.ticket,
                    'symbol': position.symbol,
                    'type': position.type,
                    'volume': position.volume,
                    'price_open': position.price_open,
                    'price_current': position.price_current,
                    'profit': position.profit,
                    'sl': position.sl,
                    'tp': position.tp,
                    'time': datetime.fromtimestamp(position.time),
                    'comment': position.comment
                })
            
            logger.info(f"📊 Found {len(position_list)} open positions")
            return position_list
            
        except Exception as e:
            logger.error(f"❌ Error getting open positions: {e}")
            return []
    
    def get_margin_usage_percent(self) -> float:
        """Calculate current margin usage as percentage"""
        account_info = self.get_account_info()
        if not account_info:
            return 0.0
        
        margin = account_info.get('margin', 0)
        equity = account_info.get('equity', 0)
        
        if equity <= 0:
            return 0.0
        
        return (margin / equity) * 100
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cache entry is still valid"""
        if key not in self._cache or key not in self._cache_timestamps:
            return False
        
        age = (datetime.now() - self._cache_timestamps[key]).total_seconds()
        return age < self.cache_timeout
    
    def clear_cache(self):
        """Clear all cached data"""
        self._cache.clear()
        self._cache_timestamps.clear()
        logger.info("🧹 MT5 cache cleared")
    
    def check_connection(self) -> bool:
        """Check if MT5 connection is still active"""
        if not self.is_connected:
            return False
        
        try:
            # Try to get account info to verify connection
            account_info = mt5.account_info()
            return account_info is not None
        except Exception as e:
            logger.error(f"❌ MT5 connection check failed: {e}")
            self.is_connected = False
            return False
    
    def reconnect(self) -> bool:
        """Attempt to reconnect to MT5"""
        logger.info("🔄 Attempting to reconnect to MT5...")
        self.shutdown()
        return self.initialize()