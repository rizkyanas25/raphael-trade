# 🎯 Raphael AI Bot - Automated Trading Signal Evaluator

**Wisdom Lord Raphael - Core Analytical Engine & Financial Risk Guard**

A sophisticated Telegram-based trading signal analysis system that combines MetaTrader 5 market data, Google Gemini AI vision capabilities, and strict risk management protocols to evaluate trading signals with precision.

## 🛡️ System Overview

Raphael AI Bot automates the process of evaluating trading signals from screenshots or text by:

- **Multi-Timeframe Analysis**: H4 → H2 → H1 → M15 technical analysis using RSI and EMA indicators
- **AI-Powered Vision**: Uses Google Gemini API to extract and analyze signal data from images
- **Strict Risk Management**: Maximum Rp 31.000 IDR risk per position with dynamic position sizing
- **Paper Trading Mode**: 2-week validation period before live deployment
- **Performance Tracking**: Comprehensive analytics with win rate, RRR, and drawdown metrics

## 🏗️ Architecture

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

## 🚀 Features

### Core Capabilities
- **Signal Analysis**: Process trading signals from images or text via Telegram
- **Multi-Timeframe Technical Analysis**: RSI(14) and EMA(20, 50, 200) across H4, H2, H1, M15
- **Risk Management**: Dynamic position sizing based on Rp 31.000 IDR max risk
- **RRR Validation**: Minimum 1:2 (intraday) or 1:3 (swing) risk-reward ratio
- **Paper Trading**: Virtual trading environment for system validation
- **Performance Analytics**: Win rate, average RRR, maximum drawdown tracking

### Raphael Protocol Output
Each analysis follows the strict structural output:

```
<< Kakunin >>
- Data verification & account status
- Balance, Equity, and active positions

<< Kai >>
- Technical analysis & strategic optimization
- Risk & reward calculations
- Multi-timeframe appraisal

<< Koku >>
- Final decision (EXECUTE/SKIP)
- MT5 parameters for execution
```

## 📋 Requirements

- **Python**: 3.11+
- **Operating System**: macOS (tested on MacBook Air M3)
- **MT5 Terminal**: HFM or compatible broker
- **Telegram Bot Token**: From @BotFather
- **Gemini API Key**: From Google AI Studio

## 🔧 Installation

### 1. Clone and Setup
```bash
cd /Users/rizkyanasbukhori/PlayWorks/raphael-trade
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configuration
Copy the example environment file and add your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your actual values:

```env
# Telegram Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_USER_ID=your_telegram_user_id_here

# Gemini AI Configuration
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.0-flash

# MT5 Configuration
MT5_LOGIN=your_mt5_login
MT5_PASSWORD=your_mt5_password
MT5_SERVER=your_mt5_server
MT5_PATH=/path/to/mt5/terminal

# Risk Management Configuration
MAX_RISK_IDR=31000
DEFAULT_LOT_SIZE=0.01
MIN_RRR_INTRADAY=2.0
MIN_RRR_SWING=3.0

# Paper Trading Configuration
PAPER_TRADING_ENABLED=true
PAPER_TRADING_DURATION_WEEKS=2
PAPER_TRADING_WIN_RATE_THRESHOLD=55.0
PAPER_TRADING_RRR_THRESHOLD=3.0
```

### 3. MT5 Setup
- Ensure MT5 terminal is running and logged into your trading account
- Enable Algo Trading in MT5 terminal
- Configure the MT5 path in your `.env` file if needed

## 🎮 Usage

### Starting the Bot
```bash
python main.py
```

### Telegram Commands
- `/start` - Initialize Raphael and welcome message
- `/help` - Show available commands and help guide
- `/status` - System health check
- `/balance` - Account balance and equity information
- `/positions` - Current open positions
- `/performance` - Trading performance metrics
- `/paper` - Paper trading status and controls

### Signal Analysis
1. **Image Analysis**: Send a trading signal screenshot to the bot
2. **Text Analysis**: Paste signal text directly in Telegram
3. **Wait for Analysis**: Raphael will process using MT5 data and AI
4. **Receive Decision**: Get structured analysis with <<Kakunin>>, <<Kai>>, <<Koku>>

## 🛡️ Risk Management Rules

### Position Sizing
- **Maximum Risk**: Rp 31.000 IDR per position
- **Dynamic Lot Size**: Automatically calculated based on SL distance
- **JPY Pairs**: Maximum 30 pips SL
- **USD Pairs**: Maximum 20 pips SL

### RRR Requirements
- **Intraday (M15/H1)**: Minimum 1:2 risk-reward ratio
- **Swing (H2/H4)**: Minimum 1:3 risk-reward ratio

### Position Limits
- **Maximum Positions**: 3 concurrent positions
- **Margin Usage**: Maximum 50% of equity
- **High Volatility**: Skip JPN225/Gold if equity < Rp 1.000.000

## 📝 Paper Trading

### Validation Phase
- **Duration**: 2 weeks minimum
- **Performance Thresholds**:
  - Win Rate: > 55%
  - Average RRR: > 1:3
  - Positive P/L required

### Transition to Live Trading
1. Complete 2-week paper trading period
2. Achieve performance thresholds
3. Disable paper trading in configuration
4. Monitor initial live trades closely

## 📊 Project Structure

```
raphael-trade/
├── main.py                          # Application entry point
├── config.py                        # Configuration management
├── requirements.txt                 # Python dependencies
├── .env.example                    # Environment variables template
├── mt5_module/                      # MT5 integration
│   ├── mt5_connector.py            # MT5 connection and data fetching
│   └── indicators.py               # Technical indicator calculations
├── telegram_module/                # Telegram bot interface
│   ├── telegram_bot.py             # Bot logic and message handlers
│   └── response_formatter.py      # Response formatting
├── ai_module/                       # AI integration
│   └── gemini_client.py            # Gemini API client
├── risk_management/                # Risk management
│   ├── risk_manager.py             # Position sizing and validation
│   └── pip_calculator.py           # Pip value calculations
├── database/                       # Data persistence
│   └── database.py                 # SQLite database operations
├── paper_trading/                  # Paper trading
│   └── paper_trading.py            # Virtual trading engine
└── utils/                          # Utilities
    ├── logger.py                   # Logging configuration
    └── retry_queue.py              # Retry mechanism
```

## 🔍 Monitoring & Logs

### Log Files
- **Location**: `raphael.log` (configurable)
- **Rotation**: 10MB max size, 5 backup files
- **Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL

### Health Monitoring
- MT5 connection status
- AI API availability
- Database operations
- Paper trading performance

## ⚠️ Important Notes

### Safety First
- **Paper Trading Enabled by Default**: System starts in paper trading mode
- **Manual Execution**: Bot provides analysis only, user executes trades manually
- **Strict Risk Limits**: Hard-coded maximum risk per position
- **Comprehensive Logging**: All operations logged for audit trail

### Operational Requirements
- **24/7 Operation**: System designed to run continuously
- **Sleep Prevention**: Use `caffeinate` or Amphetamine on macOS
- **Internet Connection**: Stable connection required for MT5 and AI APIs
- **MT5 Terminal**: Must remain running and connected

### Error Handling
- **Automatic Retry**: Failed operations queued with exponential backoff
- **Graceful Degradation**: System continues with cached data on failures
- **Telegram Alerts**: System failures sent via Telegram messages

## 🐛 Troubleshooting

### MT5 Connection Issues
```bash
# Check MT5 terminal is running
# Verify login credentials in .env
# Check MT5 path configuration
```

### AI API Errors
```bash
# Verify Gemini API key is valid
# Check API quota and limits
# Review error logs in raphael.log
```

### Database Issues
```bash
# Check database file permissions
# Verify SQLite is working
# Review database connection logs
```

## 📈 Performance Optimization

### System Performance
- **Caching**: MT5 data cached for 60 seconds
- **Async Operations**: Concurrent data fetching
- **Connection Pooling**: Database connection reuse

### Response Time
- **Target**: < 30 seconds from signal input to analysis output
- **Optimization**: Image compression before AI processing
- **Memoization**: Indicator calculation caching

## 🔒 Security

### API Key Management
- **Environment Variables**: All sensitive data in `.env` file
- **No Hardcoding**: API keys never committed to code
- **Access Control**: Telegram bot restricted to authorized user ID

### Data Protection
- **Local Storage**: All data stored locally on your machine
- **No Cloud Sync**: Database and logs remain local
- **Audit Trail**: Comprehensive logging of all operations

## 🚀 Future Enhancements

### Planned Features
- Multi-timeframe backtesting
- Market sentiment analysis
- Portfolio optimization
- Web dashboard for monitoring
- Mobile app for faster signal input

### Scalability
- Multi-user support
- Cloud deployment options
- Enhanced database options
- API for third-party integration

## 📞 Support

For issues or questions:
1. Check the logs in `raphael.log`
2. Review the troubleshooting section
3. Verify all configuration in `.env`
4. Ensure MT5 terminal is running properly

## 📄 License

This project is developed for personal trading use by Nyunk-sama.

## 🙏 Acknowledgments

- **MetaTrader 5** for market data access
- **Google Gemini** for AI vision capabilities
- **Telegram** for bot platform
- **Python Community** for excellent libraries

---

**🛡️ Wisdom Lord Raphael - Core Analytical Engine & Financial Risk Guard**

*Precision. Analysis. Risk Management. No Compromise.*