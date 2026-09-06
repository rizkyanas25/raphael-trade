# Product Requirement Document (PRD): Automated Trading Signal Evaluator (Raphael AI Bot)

## 1. System Overview & Objectives

* **System Purpose**: Mengotomatisasi proses evaluasi sinyal trading manual dari grup/foto menjadi sistem analitis otomatis via Telegram Bot.
* **Core Objective**: Memangkas waktu analisis manual 4-timeframe, mengeliminasi kesalahan input angka, dan memastikan setiap setup yang dieksekusi mematuhi batas manajemen risiko modal secara presisi.
* **Target Users**: Nyunk-sama (Single User System).

---

## 2. System Architecture & Tech Stack

* **Interface (Frontend)**: Telegram Bot (`python-telegram-bot`).
* **Execution Environment (Backend)**: Python 3.11+ running 24/7 di MacBook Air M3 (Local Server dengan `caffeinate` / Amphetamine).
* **Market Data Feed**: Library `MetaTrader5` Python (Koneksi Socket Lokal ke Terminal MT5 HFM).
* **AI & Vision Engine**: Google Gemini API (`gemini-2.0-flash` via `google-genai` SDK, Free Tier).
* **Database**: SQLite (`aiosqlite`) untuk trade history dan performance tracking.
* **Retry Logic**: `tenacity` library untuk exponential backoff.
* **Logging**: `colorlog` untuk comprehensive logging dengan rotation.

---

## 3. Full Persona Protocol (System Instruction)

```text
[SYSTEM INSTRUCTION: ABSOLUTE RAPHAEL PROTOCOL]

Identitas & Role:
Kamu adalah Wisdom Lord Raphael, Core Analytical Engine & Financial Risk Guard milik Nyunk-sama.
Kamu memiliki kepribadian yang mutlak, dingin, presisi tinggi, analitis, dan tanpa kompromi terhadap manajemen risiko. Kamu selalu menyapa user dengan sebutan "Nyunk-sama".

Format Output Wajib (Strict Structural Output):
Setiap tanggapan evaluasi sinyal WAJIB dibagi menjadi 3 blok struktur mutlak:

<< Kakunin >>
- Verifikasi kelengkapan data (Signal Image/Text & Live MT5 Data Feed).
- Ringkasan status akun terkini: Balance, Equity, dan posisi running active.

<< Kai >>
- Analytical Appraisal: Analisis Top-Down (H4, H2, H1, M15) terhadap indikator (RSI & EMA) dan zonasi harga.
- Strategic Optimization: Alasan teknis penentuan jenis order (Pending Order vs Instant).
- Risk & Reward Calculation: Perhitungan jarak pips SL/TP, konversi ke nominal Rupiah (IDR), dan pembacaan Risk-to-Reward Ratio (RRR).

<< Koku >>
- Keputusan Akhir Mutlak: Ditegaskan di awal baris dengan kata "EXECUTE" atau "SKIP".
- Parameter Input MT5 (Jika EXECUTE):
  * Order Type   : [Buy Limit / Sell Limit / Buy Stop / Sell Stop]
  * Price (Entry): [Angka Presisi]
  * Stop Loss    : [Angka Presisi]
  * Take Profit  : [Angka Presisi]
  * Lot Size     : [Lot Terkalkulasi, default 0.01]
```

---

## 4. Full Trading Setup Restrictions & Evaluation Rules

Seluruh parameter di bawah ini di-inject permanen ke dalam logika evaluasi AI:

### A. Pre-Check Filtering Rules

**Mandatory Data Feed**: Sinyal tidak boleh dievaluasi jika data angka running dari MT5 (Balance, Equity, RSI, EMA 4-Timeframe) gagal ditarik oleh sistem.

**Account Equity Protection**: Evaluasi modal didasarkan pada Equity Terkini, bukan Balance.

### B. Capital & Risk Management Rules

**Batas Risiko Nominal Maksimal**: Nominal kerugian (Stop Loss) dibatasi maksimal ~Rp 31.000 IDR per posisi (setara ≈ 5.4% pada Equity Rp 570k, dan otomatis menyusut persentasenya menuju 3% saat Equity mencapai target Rp 1.000.000 IDR).

**Konversi Pips ke IDR (0.01 Lot)**:
- Pair USD Major (EURUSD, AUDUSD, dsb): 1 Pip ≈ Rp 1.550 IDR. Jarak SL maksimal 20.0 Pips.
- Pair JPY Cross (GBPJPY, dsb): 1 Pip ≈ Rp 1.050 IDR. Jarak SL maksimal 30.0 Pips.
- Cross Pair Lain (NZDCAD, CADCHF, dsb): Wajib menyesuaikan kalkulasi pip value lokal terhadap mata uang dasar IDR.

**Penyelarasan Lot Size**: Jika jarak SL bawaan sinyal terlalu lebar, Lot Size WAJIB diturunkan, atau titik Entry disesuaikan (re-entry via Pending Order) agar nominal risiko kerugian TIDAK MELEBIHI Rp 31.000 IDR.

### C. Order Strategy & Market Mechanics Rules

**Utamakan Pending Order**: Rekomendasi wajib memprioritaskan Pending Order (Sell Limit / Buy Limit) pada area PRZ (Potential Reversal Zone) / Supply-Demand Zone.

DILARANG merekomendasikan Instant Execution jika struktur micro M15 sedang dalam fase counter-trend retracement yang berisiko tersapu koreksi.

**Karakteristik Instrument Handling**:
- Forex Major / Cross: Diizinkan untuk dievaluasi harian (Intraday / Swing).
- Indeks Volatilitas Tinggi (JPN225 / Gold): WAJIB diberikan keputusan SKIP jika Equity akun masih di bawah Rp 1.000.000 IDR karena risiko margin spike.

### D. Multi-Timeframe Integration (Top-Down Analysis Rules)

**H4 & H2 (Macro Structure)**: Menentukan arah tren utama, area oversold/overbought RSI, dan zona Supply/Demand utama.

**H1 (Intermediate Barrier)**: Mengonfirmasi kelogisan jarak Take Profit (TP) agar tidak terhadang dynamic resistance/support.

**M15 (Micro Entry Refinement)**: Menentukan titik jemput (trigger price) dan presisi Stop Loss agar rapat.

**Minimum Risk-to-Reward Ratio (RRR)**:
- Setup Intraday (M15/H1): Minimal 1 : 2.0.
- Setup Swing (H2/H4): Minimal 1 : 3.0 hingga 1 : 6.5.

---

## 5. Functional Requirements & User Flow

```
[iPhone 13]                                 [MacBook Air M3 Local Server]
   |                                                      |
   |-- (1. Forward/Foto Sinyal via Telegram) ----------->|
   |                                                      |-- (2. Extract Image/Text)
   |                                                      |-- (3. Call MT5 API: Get Equity & RSI/EMA M15-H4)
   |                                                      |-- (4. Send Payload + System Instruction to Gemini)
   |                                                      |-- (5. Gemini Processes Evaluation)
   |<-- (6. Send Structured Response <<Koku>>) -----------|
```

### Input Handling
- Bot menerima input berupa gambar (screenshot sinyal) atau pesan teks dari Telegram.
- Automated Data Extraction: Python Backend secara otomatis menarik snapshot JSON dari MT5:
  - `account_info`: Balance, Equity, Free Margin.
  - `symbol_data`: Bid, Ask, Spread.
  - `indicators`: RSI(14) dan EMA(20, 50, 200) untuk timeframe M15, H1, H2, dan H4.

### Payload Synthesis
- Menggabungkan foto/teks sinyal + JSON data MT5 + System Instruction (Raphael Protocol), lalu mengirimkannya ke Gemini `gemini-2.0-flash`.

### Output Rendering
- Bot membalas pesan pengguna di Telegram dengan format Markdown yang rapi dan scannable.

---

## 6. Technical Implementation Details

### 6.1 Configuration Management
- Environment variables via `.env` file
- Required variables: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_USER_ID`, `GEMINI_API_KEY`, `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`
- Risk parameters: `MAX_RISK_IDR=31000`, `DEFAULT_LOT_SIZE=0.01`, `MIN_RRR_INTRADAY=2.0`, `MIN_RRR_SWING=3.0`

### 6.2 MT5 Integration
- Connection management with automatic reconnection
- Data caching with 60-second timeout
- Error handling with retry logic (max 3 attempts, exponential backoff)
- Support for multiple symbols and timeframes

### 6.3 Telegram Bot Interface
- Commands: `/start`, `/help`, `/status`, `/balance`, `/positions`, `/performance`, `/paper`
- Image and text message handlers for signal input
- Inline keyboard for paper trading controls
- User authorization via Telegram user ID

### 6.4 AI Integration
- Gemini Vision API for image analysis
- Structured output parsing with <<Kakunin>>, <<Kai>>, <<Koku>> format
- Rate limiting and error handling
- Processing time tracking

### 6.5 Risk Management Engine
- Position sizing based on Rp 31.000 IDR max risk
- Dynamic lot size calculation
- RRR validation (1:2 intraday, 1:3 swing)
- Pip value calculations per instrument type
- Position limits based on margin usage

### 6.6 Database Schema
- **trades table**: Signal data, entry/exit prices, P/L, RRR, paper trade flag
- **performance_metrics table**: Win rate, total P/L, drawdown statistics
- **system_state table**: Key-value pairs for system recovery
- **signal_analysis table**: AI evaluation history with full context

### 6.7 Paper Trading Mode
- Virtual equity tracking (starting Rp 570k)
- Simulated trade execution
- Performance validation over 2-week period
- Readiness assessment for live trading

---

## 7. User Decisions & Configuration

### Execution Model
- **Analysis Only**: Bot provides recommendations, user executes trades manually
- No automatic order execution via MT5 API

### Error Handling
- **Queue & Retry**: Exponential backoff for MT5 and API failures
- Graceful degradation with cached data
- Telegram alerts for system failures

### Data Persistence
- **Full Tracking**: SQLite database for trade history and performance metrics
- Comprehensive logging with rotation (10MB max, 5 backups)

### Paper Trading Configuration
- **Duration**: 2 weeks minimum before live deployment
- **Performance Thresholds**: Win rate > 55%, RRR > 1:3
- **Transition**: Manual disable after meeting thresholds

---

## 8. System Architecture Diagram

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Telegram Bot   │───▶│   AI Engine     │───▶│  Risk Manager   │
│  (Interface)    │    │  (Gemini API)   │    │  (Positioning)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       ▼                       │
         │              ┌─────────────────┐              │
         └──────────────│   MT5 Data      │──────────────┘
                        │   (Market Data) │
                        └─────────────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │   Database      │
                        │  (SQLite)       │
                        └─────────────────┘
```

---

## 9. Security & Reliability

### Security Measures
- Environment variables for all sensitive data
- Telegram bot restricted to authorized user ID only
- No API keys hardcoded in source code
- Local-only data storage (no cloud sync)

### Reliability Features
- Automatic retry with exponential backoff
- MT5 connection monitoring and recovery
- Comprehensive error logging
- Telegram alerts for system failures
- State persistence for crash recovery

---

## 10. Performance Requirements

### Response Time
- Target: < 30 seconds from signal input to analysis output
- Image processing optimization
- Data caching to reduce API calls

### System Uptime
- Target: 99%+ uptime
- Automatic recovery from failures
- Sleep prevention on macOS (caffeinate/Amphetamine)

### Data Freshness
- MT5 data cache: 60 seconds
- Real-time price updates for active analysis
- Configurable refresh intervals

---

## 11. Testing & Validation

### Paper Trading Phase
- **Duration**: 2 weeks minimum
- **Minimum Trades**: 10 trades
- **Success Criteria**:
  - Win rate > 55%
  - Average RRR > 1:3
  - Positive total P/L

### Testing Strategy
- Unit tests for individual modules
- Integration tests for MT5 + AI flow
- Paper trading validation
- Performance metrics tracking

---

## 12. Deployment Requirements

### Environment Setup
- Python 3.11+ with virtual environment
- MT5 terminal running and connected
- Stable internet connection
- macOS with sleep prevention

### Installation Steps
1. Clone repository
2. Create virtual environment
3. Install dependencies: `pip install -r requirements.txt`
4. Configure `.env` file with API keys
5. Start MT5 terminal
6. Run bot: `python main.py`

### Operational Requirements
- 24/7 operation capability
- Manual sleep prevention during testing
- Regular monitoring of logs
- Backup of database file

---

## 13. Monitoring & Maintenance

### Logging
- Comprehensive logging to `raphael.log`
- Color-coded console output
- Automatic log rotation (10MB, 5 backups)
- Different log levels for different components

### Health Monitoring
- MT5 connection status
- AI API availability
- Database operation status
- Paper trading performance metrics

### Maintenance Tasks
- Regular log review
- Database backup
- Performance analysis
- System health checks

---

## 14. Future Enhancements

### Planned Features
- Multi-timeframe backtesting
- Market sentiment analysis integration
- Portfolio optimization algorithms
- Web dashboard for monitoring
- Mobile app for faster signal input

### Scalability Options
- Multi-user support
- Cloud deployment options
- Enhanced database options (PostgreSQL)
- API for third-party integration

---

## 15. Success Metrics

### Technical Metrics
- System uptime: > 99%
- Response time: < 30 seconds
- Error rate: < 1%
- MT5 connection success: > 95%

### Trading Metrics
- Paper trading win rate: > 55%
- Average RRR: > 1:3
- Maximum drawdown: < 15%
- Positive expectancy over validation period

---

## 16. Risk Mitigation

### Technical Risks
- **MT5 Disconnection**: Automatic reconnection with retry logic
- **API Rate Limits**: Rate limiting and queue management
- **Image Processing Fallback**: Text input as alternative
- **Database Corruption**: Regular backups and integrity checks

### Trading Risks
- **Slippage**: Paper trading to estimate real-world impact
- **Gap Risk**: Time-based order cancellation
- **Model Accuracy**: Continuous performance monitoring
- **Overfitting**: Regular validation against new data

---

## 17. Documentation Requirements

### User Documentation
- Installation guide
- Configuration instructions
- Command reference
- Troubleshooting guide

### Technical Documentation
- API documentation
- Database schema
- Module dependencies
- Code comments for complex logic

---

## 18. Compliance & Best Practices

### Coding Standards
- PEP 8 compliance
- Type hints for all functions
- Comprehensive docstrings
- Error handling for all external calls

### Security Best Practices
- No hardcoded credentials
- Input validation
- SQL injection prevention
- Secure API communication

---

## 19. Version Control

### Git Strategy
- Main branch for production
- Feature branches for new developments
- Pull request requirements
- Automated testing on commits

### Release Management
- Semantic versioning
- Changelog maintenance
- Backward compatibility considerations
- Database migration scripts

---

## 20. Support & Communication

### Issue Resolution
- GitHub issues for bug reports
- Documentation for common problems
- Log analysis for debugging
- User feedback integration

### Continuous Improvement
- Performance metric tracking
- User experience optimization
- Technology stack updates
- Feature request evaluation

---

**Document Version**: 1.0  
**Last Updated**: 2026-09-04  
**Status**: Implementation Complete  
**Next Phase**: Deployment & Testing