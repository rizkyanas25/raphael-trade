# 🚀 Raphael AI Bot - Setup Guide for Python Beginners

Complete guide to get Raphael AI Bot running from scratch. This guide assumes you're familiar with JavaScript but new to Python.

## 📋 Prerequisites Checklist

Before starting, make sure you have:

- [ ] Python 3.11+ installed on your Mac
- [ ] MT5 Terminal installed and running
- [ ] Active trading account with HFM or compatible broker
- [ ] Telegram account
- [ ] Google account (for Gemini API)

---

## 🔑 Step 1: Get Your API Keys & Credentials

### 1.1 Telegram Bot Token & User ID

**Get Telegram Bot Token:**
1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow the instructions
3. Choose a name (e.g., "Raphael Trading Bot")
4. Choose a username (e.g., "raphael_trading_bot")
5. BotFather will give you a token like: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`

**Get Your Telegram User ID:**
1. Open Telegram and search for `@userinfobot`
2. Send `/start`
3. Bot will reply with your user ID (numbers only)

### 1.2 Google Gemini API Key

**Get Gemini API Key:**
1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the API key (starts with `AIza...`)

### 1.3 MT5 Account Credentials

**Get MT5 Login Details:**
1. Open your MT5 Terminal
2. Go to File → Login to Trade Account
3. Note down:
   - **Login number** (your account number)
   - **Password** (your trading password)
   - **Server** (e.g., "HFM-Demo" or "HFMReal")

---

## 📁 Step 2: Create Your .env File

In Python, we use `.env` files just like in JavaScript! The system uses `python-dotenv` library to load them.

### 2.1 Copy the Example File

```bash
# In your project directory
cp .env.example .env
```

### 2.2 Edit the .env File

Open `.env` in your text editor and fill in your actual values:

```env
# Telegram Configuration
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_USER_ID=123456789

# Gemini AI Configuration  
GEMINI_API_KEY=AIzaSyABC123xyz...
GEMINI_MODEL=gemini-2.0-flash

# MT5 Configuration
MT5_LOGIN=12345678
MT5_PASSWORD=your_mt5_password
MT5_SERVER=HFM-Demo
MT5_PATH=/Applications/MetaTrader 5.app/Contents/MacOS/terminal

# Risk Management Configuration
MAX_RISK_IDR=31000
DEFAULT_LOT_SIZE=0.01
MIN_RRR_INTRADAY=2.0
MIN_RRR_SWING=3.0

# Pip Values (IDR per pip for 0.01 lot)
PIP_VALUE_USD_MAJOR=1550
PIP_VALUE_JPY_CROSS=1050
MAX_SL_PIPS_USD=20.0
MAX_SL_PIPS_JPY=30.0

# Position Limits
MAX_POSITIONS=3
MAX_MARGIN_USAGE_PERCENT=50.0

# Paper Trading Configuration
PAPER_TRADING_ENABLED=true
PAPER_TRADING_DURATION_WEEKS=2
PAPER_TRADING_WIN_RATE_THRESHOLD=55.0
PAPER_TRADING_RRR_THRESHOLD=3.0

# Database Configuration
DATABASE_PATH=raphael_trades.db

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=raphael.log

# Retry Configuration
MAX_RETRY_ATTEMPTS=3
RETRY_DELAY_SECONDS=5

# System Configuration
SYSTEM_TIMEZONE=Asia/Jakarta
```

### Important Notes:
- **Never commit `.env` to git** (it's already in `.gitignore`)
- **Replace ALL placeholder values** with your actual credentials
- **Keep your .env file secure** - it contains sensitive data

---

## 🐍 Step 3: Set Up Python Environment

### 3.1 Check Python Version

```bash
python3 --version
# Should show Python 3.11.x or higher
```

If you don't have Python 3.11+, install it:
```bash
# Using Homebrew (recommended for Mac)
brew install python@3.11
```

### 3.2 Create Virtual Environment

In Python, we use virtual environments (like `node_modules` in JS):

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate
```

You'll see `(venv)` in your terminal prompt when activated.

### 3.3 Install Dependencies

```bash
# Install most required packages
pip install -r requirements.txt
```

**✅ MetaTrader5 for macOS (mt5-mac):**
For macOS (especially Apple Silicon M1/M2/M3), we use `mt5-mac` which is designed specifically for Mac:

```bash
# Install mt5-mac (works with MetaTrader 5.app on macOS)
pip install mt5-mac
```

**Requirements for mt5-mac:**
- MetaTrader 5.app installed on your Mac (download from https://www.metatrader5.com/en/download)
- Python 3.9+ (you should have this)
- Internet connection for first-time setup (~8MB download)

**How mt5-mac works:**
1. Automatically finds your MetaTrader 5.app in `/Applications`
2. Downloads Python 3.9 for Windows (one-time, ~8MB)
3. Installs the MetaTrader5 package inside MT5's Wine environment
4. Connects directly to your running MT5 terminal

**If mt5-mac doesn't work:**
The system will automatically fall back to mock mode for testing.

---

## 🖥️ Step 4: Prepare MT5 Terminal

### 4.1 Start MT5 Terminal

1. Open your MT5 Terminal
2. Login to your trading account
3. **Important**: Keep MT5 running while the bot is active

### 4.2 Enable Algo Trading

1. In MT5, go to Tools → Options → Expert Advisors
2. Check "Allow algorithmic trading"
3. Click OK

### 4.3 Verify MT5 Installation

Make sure MetaTrader 5.app is installed in `/Applications/`:
```bash
# Check if MT5 is installed
ls /Applications/ | grep "MetaTrader"
```

Should show: `MetaTrader 5.app`

If not installed, download from: https://www.metatrader5.com/en/download

---

## 🚀 Step 5: Run the Application

### 5.1 Start the Bot

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Run the bot
python main.py
```

### 5.2 What You Should See

```
🎯 Wisdom Lord Raphael - Core Analytical Engine & Financial Risk Guard
🚡 Initializing Raphael AI Bot System...
✅ Configuration loaded successfully
✅ Database initialized successfully
✅ MT5 connector initialized successfully
✅ Telegram bot initialized successfully
🎉 Raphael AI Bot is ready to serve Nyunk-sama!
📡 Waiting for trading signals via Telegram...
```

### 5.3 Test the Bot

1. Open Telegram
2. Find your bot (search for the username you created)
3. Send `/start`
4. You should see the welcome message from Raphael

---

## 🧪 Step 6: Test Basic Commands

Try these commands in Telegram:

- `/start` - Initialize the bot
- `/help` - Show available commands
- `/status` - Check system health
- `/balance` - See account balance
- `/paper` - Check paper trading status

---

## 📸 Step 7: Test Signal Analysis

### Test with Text Signal:
Send a message like:
```
EURUSD BUY LIMIT @ 1.0850
SL: 1.0830
TP: 1.0910
```

### Test with Image:
Send a screenshot of a trading signal.

The bot should analyze it and respond with the structured <<Kakunin>>, <<Kai>>, <<Koku>> format.

---

## ⚠️ Troubleshooting

### Python Not Found
```bash
# If you get "python: command not found"
# Use python3 instead:
python3 main.py
```

### Module Import Errors
```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### MT5 Connection Issues
1. Make sure MT5 terminal is running
2. Check your MT5 credentials in `.env`
3. Verify MT5 path is correct
4. Try restarting MT5 terminal

### Telegram Bot Not Responding
1. Check your bot token is correct
2. Verify your user ID matches
3. Check the bot logs in `raphael.log`
4. Make sure you've started a conversation with the bot

### Gemini API Errors
1. Verify your API key is correct
2. Check if you have API quota available
3. Ensure the key doesn't have spaces or extra characters

---

## 🛡️ Security Best Practices

### 1. Protect Your .env File
```bash
# Make .env readable only by you
chmod 600 .env
```

### 2. Never Share Credentials
- Never commit `.env` to git
- Never share your API keys publicly
- Never include credentials in code

### 3. Regular Updates
- Keep Python updated
- Update dependencies regularly:
  ```bash
  pip install --upgrade -r requirements.txt
  ```

---

## 📝 Python vs JavaScript Quick Reference

| JavaScript | Python | Notes |
|------------|--------|-------|
| `npm install` | `pip install` | Package installation |
| `node_modules/` | `venv/` | Dependencies folder |
| `require('dotenv')` | `python-dotenv` | Environment variables |
| `process.env.VAR` | `os.getenv('VAR')` | Access env vars |
| `console.log` | `print()` | Output to console |
| `package.json` | `requirements.txt` | Dependencies list |
| `npm start` | `python main.py` | Run application |

---

## 🎯 Next Steps After Setup

1. **Paper Trading Phase** (2 weeks)
   - Send test signals
   - Monitor performance
   - Validate AI decisions

2. **Performance Validation**
   - Achieve >55% win rate
   - Achieve >1:3 average RRR
   - Positive P/L required

3. **Go Live**
   - Disable paper trading in `.env`
   - Start with small positions
   - Monitor closely

---

## 📞 Need Help?

### Check Logs First
```bash
# View the bot logs
tail -f raphael.log
```

### Common Issues
- MT5 not running → Start MT5 terminal
- Wrong API keys → Check `.env` file
- Python version → Ensure 3.11+
- Network issues → Check internet connection

### System Status Commands
- `/status` - Check if all systems are operational
- `/balance` - Verify MT5 connection
- `/performance` - Check trading metrics

---

## 🎉 You're Ready!

Once you've completed these steps, Raphael AI Bot will be:
- ✅ Connected to MT5 for live market data
- ✅ Integrated with Gemini AI for signal analysis
- ✅ Ready to receive trading signals via Telegram
- ✅ Running in paper trading mode for validation

**Wisdom Lord Raphael is ready to serve, Nyunk-sama! 🛡️**