"""
Pip Calculator for Raphael AI Bot
Wisdom Lord Raphael - Core Analytical Engine & Financial Risk Guard
"""

import logging
from typing import Dict, Optional, Any
from config import Config


logger = logging.getLogger(__name__)


class PipCalculator:
    """Calculate pip values and distances for different trading instruments"""
    
    # Standard pip definitions for different instrument types
    PIP_DEFINITIONS = {
        'USD_MAJORS': {
            'symbols': ['EURUSD', 'GBPUSD', 'AUDUSD', 'NZDUSD', 'USDCHF', 'USDCAD'],
            'pip_size': 0.0001,
            'point_size': 0.00001
        },
        'JPY_CROSS': {
            'symbols': ['USDJPY', 'EURJPY', 'GBPJPY', 'AUDJPY', 'CADJPY', 'CHFJPY'],
            'pip_size': 0.01,
            'point_size': 0.001
        },
        'INDICES': {
            'symbols': ['US30', 'NAS100', 'JPN225', 'UK100', 'GER40'],
            'pip_size': 1.0,
            'point_size': 0.1
        },
        'COMMODITIES': {
            'symbols': ['XAUUSD', 'XAGUSD', 'XTIUSD', 'XNGUSD'],
            'pip_size': 0.01,
            'point_size': 0.001
        },
        'CRYPTO': {
            'symbols': ['BTCUSD', 'ETHUSD', 'LTCUSD'],
            'pip_size': 0.01,
            'point_size': 0.001
        }
    }
    
    def __init__(self, config: Config):
        """Initialize pip calculator with configuration"""
        self.config = config
        logger.info("📏 Pip Calculator initialized")
    
    def get_instrument_type(self, symbol: str) -> str:
        """Determine the instrument type for a given symbol"""
        symbol_upper = symbol.upper()
        
        for instrument_type, data in self.PIP_DEFINITIONS.items():
            if any(inst_symbol in symbol_upper for inst_symbol in data['symbols']):
                return instrument_type
        
        # Default to USD majors for unknown symbols
        return 'USD_MAJORS'
    
    def get_pip_size(self, symbol: str) -> float:
        """Get the pip size for a given symbol"""
        instrument_type = self.get_instrument_type(symbol)
        return self.PIP_DEFINITIONS[instrument_type]['pip_size']
    
    def get_point_size(self, symbol: str) -> float:
        """Get the point size for a given symbol"""
        instrument_type = self.get_instrument_type(symbol)
        return self.PIP_DEFINITIONS[instrument_type]['point_size']
    
    def price_to_pips(self, symbol: str, price_difference: float) -> float:
        """Convert price difference to pips"""
        pip_size = self.get_pip_size(symbol)
        if pip_size > 0:
            return abs(price_difference) / pip_size
        return 0.0
    
    def pips_to_price(self, symbol: str, pips: float) -> float:
        """Convert pips to price difference"""
        pip_size = self.get_pip_size(symbol)
        return pips * pip_size
    
    def calculate_pip_distance(
        self,
        symbol: str,
        price1: float,
        price2: float
    ) -> float:
        """Calculate the pip distance between two prices"""
        price_diff = abs(price1 - price2)
        return self.price_to_pips(symbol, price_diff)
    
    def calculate_monetary_value(
        self,
        symbol: str,
        pips: float,
        lot_size: float = 0.01
    ) -> float:
        """
        Calculate the monetary value of pip movement for a given lot size
        
        Args:
            symbol: Trading symbol
            pips: Number of pips
            lot_size: Lot size (default 0.01)
        
        Returns:
            Monetary value in base currency (typically USD)
        """
        try:
            # Get pip value from config (in IDR for 0.01 lot)
            pip_value_idr = self.config.get_pip_value(symbol)
            
            # Calculate monetary value
            monetary_value = (pips * pip_value_idr) * (lot_size / 0.01)
            
            return round(monetary_value, 2)
            
        except Exception as e:
            logger.error(f"❌ Error calculating monetary value: {e}")
            return 0.0
    
    def calculate_position_size_from_risk(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        risk_amount: float,
        account_equity: float
    ) -> Dict[str, float]:
        """
        Calculate position size based on risk amount
        
        Args:
            symbol: Trading symbol
            entry_price: Entry price
            stop_loss: Stop loss price
            risk_amount: Risk amount in IDR
            account_equity: Current account equity
        
        Returns:
            Dictionary with position sizing details
        """
        try:
            # Calculate pip distance
            pip_distance = self.calculate_pip_distance(symbol, entry_price, stop_loss)
            
            # Get pip value for 0.01 lot
            pip_value_001 = self.config.get_pip_value(symbol)
            
            # Calculate lot size
            if pip_distance > 0 and pip_value_001 > 0:
                lot_size = (risk_amount / pip_distance / pip_value_001) * 0.01
            else:
                lot_size = 0.01
            
            # Ensure reasonable bounds
            lot_size = max(0.01, min(lot_size, 1.0))
            
            # Calculate actual risk
            actual_risk = pip_distance * pip_value_001 * (lot_size / 0.01)
            
            return {
                'lot_size': round(lot_size, 2),
                'pip_distance': round(pip_distance, 1),
                'actual_risk': round(actual_risk, 2),
                'risk_percentage': (actual_risk / account_equity * 100) if account_equity > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating position size from risk: {e}")
            return {
                'lot_size': 0.01,
                'pip_distance': 0.0,
                'actual_risk': 0.0,
                'risk_percentage': 0.0
            }
    
    def format_pip_display(self, symbol: str, pips: float) -> str:
        """Format pip value for display"""
        instrument_type = self.get_instrument_type(symbol)
        
        if instrument_type == 'JPY_CROSS':
            return f"{pips:.1f} pips"
        elif instrument_type == 'INDICES':
            return f"{pips:.0f} points"
        else:
            return f"{pips:.1f} pips"
    
    def validate_stop_loss_distance(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float
    ) -> Dict[str, Any]:
        """
        Validate if stop loss distance is within acceptable limits
        
        Args:
            symbol: Trading symbol
            entry_price: Entry price
            stop_loss: Stop loss price
        
        Returns:
            Dictionary with validation results
        """
        try:
            pip_distance = self.calculate_pip_distance(symbol, entry_price, stop_loss)
            max_pips = self.config.get_max_sl_pips(symbol)
            
            is_valid = pip_distance <= max_pips
            excess_pips = max(0, pip_distance - max_pips)
            
            return {
                'is_valid': is_valid,
                'pip_distance': round(pip_distance, 1),
                'max_pips': max_pips,
                'excess_pips': round(excess_pips, 1),
                'instrument_type': self.get_instrument_type(symbol)
            }
            
        except Exception as e:
            logger.error(f"❌ Error validating stop loss distance: {e}")
            return {
                'is_valid': False,
                'pip_distance': 0.0,
                'max_pips': 0.0,
                'excess_pips': 0.0,
                'instrument_type': 'UNKNOWN'
            }