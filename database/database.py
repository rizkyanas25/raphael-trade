"""
Database Module for Raphael AI Bot
Wisdom Lord Raphael - Core Analytical Engine & Financial Risk Guard
"""

import aiosqlite
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import json

from config import Config


logger = logging.getLogger(__name__)


class Database:
    """SQLite database for trade history and performance tracking"""
    
    def __init__(self, config: Config):
        """Initialize database with configuration"""
        self.config = config
        self.db_path = Path(config.database_path)
        self.connection: Optional[aiosqlite.Connection] = None
        
    async def connect(self):
        """Establish database connection"""
        if self.connection is not None:
            return  # Already connected, skip
        self.connection = await aiosqlite.connect(self.db_path)
        self.connection.row_factory = aiosqlite.Row
        logger.info(f"✅ Database connected: {self.db_path}")
        
    async def close(self):
        """Close database connection"""
        if self.connection:
            await self.connection.close()
            logger.info("🔌 Database connection closed")
    
    async def initialize_schema(self):
        """Initialize database schema"""
        await self.connect()
        try:
            # Create trades table
            await self.connection.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_id TEXT UNIQUE,
                    symbol TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    lot_size REAL NOT NULL,
                    risk_idr REAL NOT NULL,
                    potential_reward_idr REAL NOT NULL,
                    rrr REAL NOT NULL,
                    timeframe TEXT NOT NULL,
                    strategy TEXT,
                    equity_at_entry REAL NOT NULL,
                    balance_at_entry REAL NOT NULL,
                    status TEXT DEFAULT 'pending',
                    entry_time TEXT,
                    exit_time TEXT,
                    exit_price REAL,
                    profit_loss REAL,
                    profit_loss_idr REAL,
                    pip_movement REAL,
                    paper_trade BOOLEAN DEFAULT FALSE,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create performance_metrics table
            await self.connection.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    period TEXT NOT NULL,
                    total_trades INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    losing_trades INTEGER DEFAULT 0,
                    win_rate REAL DEFAULT 0,
                    total_profit_loss REAL DEFAULT 0,
                    total_profit_loss_idr REAL DEFAULT 0,
                    avg_rrr REAL DEFAULT 0,
                    max_drawdown REAL DEFAULT 0,
                    max_drawdown_percent REAL DEFAULT 0,
                    sharpe_ratio REAL DEFAULT 0,
                    paper_trades BOOLEAN DEFAULT FALSE,
                    calculated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create system_state table for recovery
            await self.connection.execute("""
                CREATE TABLE IF NOT EXISTS system_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create signal_analysis table for AI evaluation history
            await self.connection.execute("""
                CREATE TABLE IF NOT EXISTS signal_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_id TEXT NOT NULL,
                    image_path TEXT,
                    text_content TEXT,
                    mt5_data_json TEXT,
                    ai_response_json TEXT,
                    kakunin_data TEXT,
                    kai_data TEXT,
                    koku_decision TEXT,
                    koku_parameters TEXT,
                    processing_time REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for performance
            await self.connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_trades_symbol 
                ON trades(symbol)
            """)
            
            await self.connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_trades_status 
                ON trades(status)
            """)
            
            await self.connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_trades_created_at 
                ON trades(created_at)
            """)
            
            await self.connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_signal_analysis_signal_id 
                ON signal_analysis(signal_id)
            """)
            
            await self.connection.commit()
            logger.info("✅ Database schema initialized successfully")
        except Exception as e:
            logger.error(f"❌ Error initializing database schema: {e}", exc_info=True)
            raise
    
    async def save_trade(self, trade_data: Dict[str, Any]) -> int:
        """Save trade data to database"""
        await self.connect()
        try:
            async with self.connection.execute(
                """
                INSERT INTO trades (
                    signal_id, symbol, order_type, entry_price, stop_loss, 
                    take_profit, lot_size, risk_idr, potential_reward_idr, rrr,
                    timeframe, strategy, equity_at_entry, balance_at_entry,
                    paper_trade
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade_data['signal_id'],
                    trade_data['symbol'],
                    trade_data['order_type'],
                    trade_data['entry_price'],
                    trade_data['stop_loss'],
                    trade_data['take_profit'],
                    trade_data['lot_size'],
                    trade_data['risk_idr'],
                    trade_data['potential_reward_idr'],
                    trade_data['rrr'],
                    trade_data['timeframe'],
                    trade_data.get('strategy', ''),
                    trade_data['equity_at_entry'],
                    trade_data['balance_at_entry'],
                    trade_data.get('paper_trade', False)
                )
            ) as cursor:
                await self.connection.commit()
                trade_id = cursor.lastrowid
                logger.info(f"💾 Trade saved with ID: {trade_id}")
                return trade_id
        except Exception as e:
            logger.error(f"❌ Error saving trade: {e}", exc_info=True)
            raise
    
    async def update_trade_status(
        self,
        signal_id: str,
        status: str,
        exit_price: Optional[float] = None,
        profit_loss: Optional[float] = None
    ):
        """Update trade status and exit data"""
        await self.connect()
        try:
            update_data: Dict[str, Any] = {
                'status': status,
                'updated_at': datetime.now().isoformat()
            }

            # Only set exit_time for terminal statuses
            if status in ('completed', 'expired', 'cancelled'):
                update_data['exit_time'] = datetime.now().isoformat()

            if exit_price is not None:
                update_data['exit_price'] = exit_price

            if profit_loss is not None:
                update_data['profit_loss'] = profit_loss
                update_data['profit_loss_idr'] = profit_loss  # same value, IDR account

            set_clause = ", ".join([f"{k} = ?" for k in update_data.keys()])
            values = list(update_data.values()) + [signal_id]

            await self.connection.execute(
                f"UPDATE trades SET {set_clause} WHERE signal_id = ?",
                values
            )
            await self.connection.commit()
            logger.info(f"📊 Trade {signal_id} → status: {status}")
        except Exception as e:
            logger.error(f"❌ Error updating trade status: {e}", exc_info=True)
            raise
    
    async def save_signal_analysis(self, analysis_data: Dict[str, Any]) -> int:
        """Save signal analysis data"""
        await self.connect()
        try:
            async with self.connection.execute(
                """
                INSERT INTO signal_analysis (
                    signal_id, image_path, text_content, mt5_data_json,
                    ai_response_json, kakunin_data, kai_data, koku_decision,
                    koku_parameters, processing_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis_data['signal_id'],
                    analysis_data.get('image_path', ''),
                    analysis_data.get('text_content', ''),
                    json.dumps(analysis_data.get('mt5_data', {}), default=str),
                    json.dumps(analysis_data.get('ai_response', {}), default=str),
                    analysis_data.get('kakunin_data', ''),
                    analysis_data.get('kai_data', ''),
                    analysis_data.get('koku_decision', ''),
                    json.dumps(analysis_data.get('koku_parameters', {}), default=str),
                    analysis_data.get('processing_time', 0.0)
                )
            ) as cursor:
                await self.connection.commit()
                analysis_id = cursor.lastrowid
                logger.info(f"🧠 Signal analysis saved with ID: {analysis_id}")
                return analysis_id
        except Exception as e:
            logger.error(f"❌ Error saving signal analysis: {e}", exc_info=True)
            raise
    
    async def get_open_paper_trades(self) -> List[Dict[str, Any]]:
        """Get all paper trades that are still pending or active (for monitor recovery)."""
        await self.connect()
        try:
            async with self.connection.execute(
                """
                SELECT * FROM trades
                WHERE paper_trade = 1
                  AND status IN ('pending', 'pending_trigger', 'active')
                ORDER BY created_at ASC
                """,
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"❌ Error getting open paper trades: {e}", exc_info=True)
            return []

    async def get_trade_history(
        self, 
        limit: int = 100, 
        paper_trade_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Get trade history"""
        await self.connect()
        try:
            query = """
                SELECT * FROM trades 
                WHERE paper_trade = ?
                ORDER BY created_at DESC 
                LIMIT ?
            """
            
            async with self.connection.execute(query, (paper_trade_only, limit)) as cursor:
                rows = await cursor.fetchall()
                trades = [dict(row) for row in rows]
                logger.info(f"📜 Retrieved {len(trades)} trades from history")
                return trades
        except Exception as e:
            logger.error(f"❌ Error getting trade history: {e}", exc_info=True)
            raise
    
    async def calculate_performance_metrics(
        self, 
        period: str = "all",
        paper_trade_only: bool = False
    ) -> Dict[str, Any]:
        """Calculate performance metrics for a given period"""
        await self.connect()
        try:
            # Get trades for the period
            time_filter = ""
            params = [paper_trade_only]
            
            if period != "all":
                time_filter = "AND created_at >= datetime('now', ?)"
                params.append(f"-{period}")
            
            query = f"""
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) as losing_trades,
                    AVG(CASE WHEN profit_loss > 0 THEN 1.0 ELSE 0.0 END) as win_rate,
                    SUM(profit_loss) as total_profit_loss,
                    AVG(rrr) as avg_rrr
                FROM trades 
                WHERE paper_trade = ? AND status = 'completed'
                {time_filter}
            """
            
            async with self.connection.execute(query, params) as cursor:
                row = await cursor.fetchone()
                metrics = dict(row) if row else {}
                
                # Calculate additional metrics
                if metrics.get('total_trades', 0) > 0:
                    metrics['win_rate'] = (metrics['winning_trades'] / metrics['total_trades']) * 100
                else:
                    metrics['win_rate'] = 0.0
                
                logger.info(f"📈 Performance metrics calculated for period: {period}")
                return metrics
                
        except Exception as e:
            logger.error(f"❌ Error calculating performance metrics: {e}", exc_info=True)
            raise
    
    async def save_system_state(self, key: str, value: str):
        """Save system state for recovery"""
        await self.connect()
        try:
            await self.connection.execute(
                """
                INSERT OR REPLACE INTO system_state (key, value, updated_at)
                VALUES (?, ?, ?)
                """,
                (key, value, datetime.now().isoformat())
            )
            await self.connection.commit()
            logger.debug(f"💾 System state saved: {key}")
        except Exception as e:
            logger.error(f"❌ Error saving system state: {e}", exc_info=True)
            raise
    
    async def get_system_state(self, key: str) -> Optional[str]:
        """Get system state for recovery"""
        await self.connect()
        try:
            async with self.connection.execute(
                "SELECT value FROM system_state WHERE key = ?",
                (key,)
            ) as cursor:
                row = await cursor.fetchone()
                return row['value'] if row else None
        except Exception as e:
            logger.error(f"❌ Error getting system state: {e}", exc_info=True)
            raise