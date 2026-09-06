"""
MT5 Loader - Centralized MT5 implementation selection
Wisdom Lord Raphael - Core Analytical Engine & Financial Risk Guard
"""

import logging
from typing import Tuple

logger = logging.getLogger(__name__)

def get_mt5_implementation(use_mock: bool = False) -> Tuple:
    """
    Get the appropriate MT5 implementation based on availability and config
    
    Returns:
        Tuple of (mt5_module, implementation_name, is_available)
    """
    if use_mock:
        from mt5_module import mock_mt5 as mt5
        logger.info("🧪 Using mock MT5 implementation")
        return mt5, "mock", False
    
    try:
        # Try mt5-mac first (best for macOS)
        import mt5_mac as mt5
        logger.info("✅ Using mt5-mac for macOS MT5 integration")
        return mt5, "mt5-mac", True
    except ImportError:
        try:
            # Try regular MetaTrader5
            import MetaTrader5 as mt5
            logger.info("✅ Using MetaTrader5 package")
            return mt5, "MetaTrader5", True
        except ImportError:
            # Fall back to mock
            from mt5_module import mock_mt5 as mt5
            logger.warning("⚠️  MT5 packages not available, using mock implementation")
            return mt5, "mock", False

# Default global initialization
mt5, MT5_IMPLEMENTATION, MT5_AVAILABLE = get_mt5_implementation()