"""
Database Module — Raphael AI Bot v2.0 (SMC Crypto Engine)
Wisdom Lord Raphael — Core SMC Analytical Engine & Crypto Risk Guard

SQLite schema v2.0:
  - trades      : all orders (pending, filled, closed, cancelled)
  - smc_zones   : detected Order Blocks and Liquidity Pools
  - scan_history: per-symbol scan results and Gemini decisions
  - system_state: key-value store for bot recovery / mode persistence
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

from config import Config


logger = logging.getLogger(__name__)


class Database:
    """Async SQLite database for Raphael v2.0"""

    def __init__(self, config: Config):
        self.config = config
        self.db_path = Path(config.database_path)
        self.connection: Optional[aiosqlite.Connection] = None

    # ── Lifecycle ──────────────────────────────────────────────────────────

    async def connect(self):
        if self.connection is not None:
            return
        self.connection = await aiosqlite.connect(self.db_path)
        self.connection.row_factory = aiosqlite.Row
        logger.info(f"✅ Database connected: {self.db_path}")

    async def close(self):
        if self.connection:
            await self.connection.close()
            self.connection = None
            logger.info("🔌 Database connection closed")

    async def initialize_schema(self):
        """Create all tables and indexes if they don't already exist."""
        await self.connect()
        try:
            # ── trades ────────────────────────────────────────────────────
            await self.connection.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id        TEXT PRIMARY KEY,
                    symbol          TEXT NOT NULL,
                    side            TEXT NOT NULL,          -- 'LONG' | 'SHORT'
                    order_type      TEXT NOT NULL DEFAULT 'LIMIT',
                    entry_price     REAL NOT NULL,
                    stop_loss       REAL NOT NULL,
                    take_profit     REAL NOT NULL,
                    position_size   REAL NOT NULL,
                    leverage        INTEGER NOT NULL DEFAULT 5,
                    risk_usdt       REAL NOT NULL DEFAULT 0.0,
                    rrr             REAL NOT NULL DEFAULT 0.0,
                    status          TEXT NOT NULL DEFAULT 'PENDING',
                    -- 'PENDING' | 'FILLED' | 'CLOSED_TP' | 'CLOSED_SL' | 'CANCELLED'
                    exchange_order_id TEXT,
                    pnl_usdt        REAL DEFAULT 0.0,
                    fill_price      REAL,
                    close_price     REAL,
                    filled_at       TEXT,
                    closed_at       TEXT,
                    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at      TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # ── smc_zones ─────────────────────────────────────────────────
            await self.connection.execute("""
                CREATE TABLE IF NOT EXISTS smc_zones (
                    zone_id         TEXT PRIMARY KEY,
                    symbol          TEXT NOT NULL,
                    timeframe       TEXT NOT NULL,         -- 'M15' | 'M5'
                    zone_type       TEXT NOT NULL,
                    -- 'DEMAND_OB' | 'SUPPLY_OB' | 'LIQUIDITY_EQH' | 'LIQUIDITY_EQL'
                    high_price      REAL NOT NULL,
                    low_price       REAL NOT NULL,
                    strength        TEXT DEFAULT 'NORMAL', -- 'STRONG' | 'NORMAL'
                    is_mitigated    INTEGER DEFAULT 0,
                    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # ── scan_history ──────────────────────────────────────────────
            await self.connection.execute("""
                CREATE TABLE IF NOT EXISTS scan_history (
                    scan_id         TEXT PRIMARY KEY,
                    symbol          TEXT NOT NULL,
                    h1_bias         TEXT,
                    h1_bos          TEXT,
                    m5_choch        TEXT,
                    has_valid_setup INTEGER DEFAULT 0,
                    setup_bias      TEXT,
                    skip_reason     TEXT,
                    gemini_decision TEXT,               -- 'EXECUTE' | 'SKIP' | 'UNKNOWN'
                    gemini_kakunin  TEXT,
                    gemini_kai      TEXT,
                    gemini_koku     TEXT,
                    order_params    TEXT,               -- JSON
                    processing_time REAL DEFAULT 0.0,
                    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # ── system_state ──────────────────────────────────────────────
            await self.connection.execute("""
                CREATE TABLE IF NOT EXISTS system_state (
                    key         TEXT PRIMARY KEY,
                    value       TEXT NOT NULL,
                    updated_at  TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # ── indexes ───────────────────────────────────────────────────
            for ddl in [
                "CREATE INDEX IF NOT EXISTS idx_trades_symbol   ON trades(symbol)",
                "CREATE INDEX IF NOT EXISTS idx_trades_status   ON trades(status)",
                "CREATE INDEX IF NOT EXISTS idx_trades_created  ON trades(created_at)",
                "CREATE INDEX IF NOT EXISTS idx_zones_symbol    ON smc_zones(symbol)",
                "CREATE INDEX IF NOT EXISTS idx_scan_symbol     ON scan_history(symbol)",
                "CREATE INDEX IF NOT EXISTS idx_scan_created    ON scan_history(created_at)",
            ]:
                await self.connection.execute(ddl)

            await self.connection.commit()
            logger.info("✅ Database schema v2.0 initialized")

        except Exception as e:
            logger.error(f"❌ initialize_schema: {e}", exc_info=True)
            raise

    # ── Trades ─────────────────────────────────────────────────────────────

    async def save_trade(self, trade: Dict[str, Any]) -> str:
        """
        Insert a new trade record.
        Returns trade_id.
        """
        await self.connect()
        trade_id = trade.get(
            "trade_id",
            f"trade_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        )
        try:
            await self.connection.execute(
                """
                INSERT INTO trades (
                    trade_id, symbol, side, order_type,
                    entry_price, stop_loss, take_profit,
                    position_size, leverage, risk_usdt, rrr,
                    status, exchange_order_id
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    trade_id,
                    trade["symbol"],
                    trade["side"],
                    trade.get("order_type", "LIMIT"),
                    trade["entry_price"],
                    trade["stop_loss"],
                    trade["take_profit"],
                    trade["position_size"],
                    trade.get("leverage", 5),
                    trade.get("risk_usdt", 0.0),
                    trade.get("rrr", 0.0),
                    trade.get("status", "PENDING"),
                    trade.get("exchange_order_id"),
                ),
            )
            await self.connection.commit()
            logger.info(f"💾 Trade saved: {trade_id} | {trade['symbol']} {trade['side']}")
            return trade_id
        except Exception as e:
            logger.error(f"❌ save_trade: {e}", exc_info=True)
            raise

    async def update_trade_status(
        self,
        trade_id: str,
        status: str,
        pnl_usdt: Optional[float] = None,
        close_price: Optional[float] = None,
        fill_price: Optional[float] = None,
        exchange_order_id: Optional[str] = None,
    ):
        """Update trade status and optional financial outcome fields."""
        await self.connect()
        now = datetime.now().isoformat()
        fields: Dict[str, Any] = {"status": status, "updated_at": now}

        if status == "FILLED":
            fields["filled_at"] = now
        if status in ("CLOSED_TP", "CLOSED_SL", "CANCELLED"):
            fields["closed_at"] = now
        if pnl_usdt is not None:
            fields["pnl_usdt"] = pnl_usdt
        if close_price is not None:
            fields["close_price"] = close_price
        if fill_price is not None:
            fields["fill_price"] = fill_price
        if exchange_order_id is not None:
            fields["exchange_order_id"] = exchange_order_id

        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [trade_id]

        try:
            await self.connection.execute(
                f"UPDATE trades SET {set_clause} WHERE trade_id = ?", values
            )
            await self.connection.commit()
            logger.info(f"📊 Trade {trade_id} → {status}")
        except Exception as e:
            logger.error(f"❌ update_trade_status: {e}", exc_info=True)
            raise

    async def get_active_trades(self) -> List[Dict[str, Any]]:
        """Return all PENDING and FILLED trades."""
        await self.connect()
        async with self.connection.execute(
            "SELECT * FROM trades WHERE status IN ('PENDING','FILLED') ORDER BY created_at ASC"
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def get_trade_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return most recent closed/cancelled trades."""
        await self.connect()
        async with self.connection.execute(
            """
            SELECT * FROM trades
            WHERE status IN ('CLOSED_TP','CLOSED_SL','CANCELLED')
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def count_active_positions(self) -> int:
        """Count PENDING + FILLED trades (used to enforce max_positions rule)."""
        await self.connect()
        async with self.connection.execute(
            "SELECT COUNT(*) as cnt FROM trades WHERE status IN ('PENDING','FILLED')"
        ) as cur:
            row = await cur.fetchone()
            return int(row["cnt"]) if row else 0

    async def get_performance_summary(self) -> Dict[str, Any]:
        """Calculate win rate, total PnL, and avg RRR from closed trades."""
        await self.connect()
        async with self.connection.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'CLOSED_TP' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN status = 'CLOSED_SL' THEN 1 ELSE 0 END) as losses,
                SUM(pnl_usdt) as total_pnl,
                AVG(rrr)      as avg_rrr
            FROM trades
            WHERE status IN ('CLOSED_TP','CLOSED_SL')
            """
        ) as cur:
            row = await cur.fetchone()
            if row:
                total = int(row["total"] or 0)
                wins  = int(row["wins"]  or 0)
                return {
                    "total_trades": total,
                    "wins":         wins,
                    "losses":       int(row["losses"] or 0),
                    "win_rate":     round(wins / total * 100, 1) if total > 0 else 0.0,
                    "total_pnl":    round(float(row["total_pnl"] or 0.0), 4),
                    "avg_rrr":      round(float(row["avg_rrr"] or 0.0), 2),
                }
            return {
                "total_trades": 0, "wins": 0, "losses": 0,
                "win_rate": 0.0, "total_pnl": 0.0, "avg_rrr": 0.0,
            }

    # ── SMC Zones ──────────────────────────────────────────────────────────

    async def save_smc_zones(self, symbol: str, smc_data: Dict[str, Any]):
        """
        Persist detected SMC zones (OBs + Liquidity Pools) from a scan.
        Clears stale unmitigated zones for the symbol first.
        """
        await self.connect()
        now = datetime.now().isoformat()

        # Remove old unmitigated zones for this symbol (fresh scan supersedes)
        await self.connection.execute(
            "DELETE FROM smc_zones WHERE symbol = ? AND is_mitigated = 0", (symbol,)
        )

        zones_to_insert = []

        for ob in smc_data.get("m15_obs", []):
            zone_id = f"zone_{symbol}_{now}_m15_{ob['type']}_{ob['high']:.4f}"
            zones_to_insert.append((
                zone_id, symbol, "M15",
                f"{ob['type']}_OB",
                ob["high"], ob["low"],
                ob.get("strength", "NORMAL"), 0,
            ))

        for ob in smc_data.get("m5_obs", []):
            zone_id = f"zone_{symbol}_{now}_m5_{ob['type']}_{ob['high']:.4f}"
            zones_to_insert.append((
                zone_id, symbol, "M5",
                f"{ob['type']}_OB",
                ob["high"], ob["low"],
                ob.get("strength", "NORMAL"), 0,
            ))

        for lp in smc_data.get("m15_liquidity", []):
            zone_id = f"zone_{symbol}_{now}_liq_{lp['type']}_{lp['price']:.4f}"
            zones_to_insert.append((
                zone_id, symbol, "M15",
                f"LIQUIDITY_{lp['type']}",
                lp["price"], lp["price"],
                "NORMAL", 0,
            ))

        if zones_to_insert:
            await self.connection.executemany(
                """
                INSERT OR IGNORE INTO smc_zones
                (zone_id, symbol, timeframe, zone_type, high_price, low_price, strength, is_mitigated)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                zones_to_insert,
            )

        await self.connection.commit()
        logger.debug(f"💾 SMC zones saved for {symbol}: {len(zones_to_insert)} zones")

    # ── Scan History ───────────────────────────────────────────────────────

    async def save_scan(self, scan: Dict[str, Any]) -> str:
        """Persist a full scan result (SMC + Gemini decision) to scan_history."""
        await self.connect()
        scan_id = scan.get(
            "scan_id",
            f"scan_{scan.get('symbol','X')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        parsed = scan.get("parsed_response", {})
        try:
            await self.connection.execute(
                """
                INSERT INTO scan_history (
                    scan_id, symbol,
                    h1_bias, h1_bos, m5_choch,
                    has_valid_setup, setup_bias, skip_reason,
                    gemini_decision, gemini_kakunin, gemini_kai, gemini_koku,
                    order_params, processing_time
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    scan_id,
                    scan.get("symbol"),
                    scan.get("h1_bias"),
                    scan.get("h1_bos"),
                    scan.get("m5_choch"),
                    int(scan.get("has_valid_setup", 0)),
                    scan.get("setup_bias"),
                    scan.get("skip_reason"),
                    parsed.get("decision"),
                    parsed.get("kakunin", ""),
                    parsed.get("kai", ""),
                    parsed.get("koku", ""),
                    json.dumps(parsed.get("parameters", {})),
                    scan.get("processing_time", 0.0),
                ),
            )
            await self.connection.commit()
            logger.info(
                f"💾 Scan saved: {scan_id} | "
                f"{scan.get('symbol')} → {parsed.get('decision')}"
            )
            return scan_id
        except Exception as e:
            logger.error(f"❌ save_scan: {e}", exc_info=True)
            raise

    async def get_recent_scans(
        self, symbol: Optional[str] = None, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Fetch recent scan history, optionally filtered by symbol."""
        await self.connect()
        if symbol:
            query = (
                "SELECT * FROM scan_history WHERE symbol = ? "
                "ORDER BY created_at DESC LIMIT ?"
            )
            params = (symbol, limit)
        else:
            query = "SELECT * FROM scan_history ORDER BY created_at DESC LIMIT ?"
            params = (limit,)

        async with self.connection.execute(query, params) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    # ── System State ───────────────────────────────────────────────────────

    async def set_state(self, key: str, value: str):
        """Upsert a key-value system state entry."""
        await self.connect()
        await self.connection.execute(
            """
            INSERT OR REPLACE INTO system_state (key, value, updated_at)
            VALUES (?, ?, ?)
            """,
            (key, value, datetime.now().isoformat()),
        )
        await self.connection.commit()

    async def get_state(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieve a system state value by key."""
        await self.connect()
        async with self.connection.execute(
            "SELECT value FROM system_state WHERE key = ?", (key,)
        ) as cur:
            row = await cur.fetchone()
            return row["value"] if row else default
