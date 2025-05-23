# LHL Pattern Trading Bot

## Objective
This project implements a trading strategy focused on identifying potential uptrends by entering long positions at consecutive support levels formed by prior valleys. The strategy aims to capture significant profit when a support level holds and an uptrend begins, while accepting small losses on initial failed entries.

The bot will:
- Use a CSV file for initial historical data setup.
- Poll for real-time price updates.
- Identify and track support and resistance levels.
- Execute trades based on the LHL (Low-High-Low) pattern and S/R levels.

## Project Structure
- `support_resistance.py`: Calculates support and resistance levels.
- `trading_bot.py`: Contains the main trading bot logic.
- `backtesting.py`: Module for backtesting the trading strategy.
- `data_fetcher.py`: Handles fetching historical and real-time price data (e.g., via CCXT).
- `utils.py`: Contains utility functions (API interaction, error handling, etc.).
- `lhl.txt`: Document outlining the strategy and project details.
- `requirements.txt`: Lists Python dependencies.
- `install_dependencies.bat`: Batch file to install Python dependencies.
- `run_trading_bot.bat`: Batch file to start the trading bot.
- `run_backtest_preliminaries.bat`: Batch file to run backtesting preliminaries.
- `generate_sr_levels.bat`: Batch file to generate a CSV file of support and resistance levels from `market_data.csv`.

## Setup
1.  **Clone the repository** (if applicable).
2.  **Install Python 3.x** if you haven't already.
3.  **Install dependencies**:
    - Open a command prompt or terminal in the project directory.
    - Run the `install_dependencies.bat` script by double-clicking it or typing `install_dependencies.bat` and pressing Enter. This will install all necessary Python packages.
4.  **Create and Configure `config.ini`**:
    - Locate the file named `config.ini` in the project directory. If it doesn't exist, you may need to create it based on the example below (e.g., by copying `config.ini.template` if one was provided, or creating it manually).
    - Open `config.ini` with a text editor.
    - Fill in your Bitget API credentials under the `[BITGET]` section.
    - Configure your trading parameters under the `[TRADING]` section (e.g., symbol, margin, leverage).
    - Specify the filename for your historical data CSV file for the trading bot under `[TRADING]` (key: `HISTORICAL_DATA_CSV`). This should be set to `market_data.csv`, and this file must be placed in the main project folder.
    - Specify the filename for your backtesting data CSV file under the `[DATA]` section (key: `BACKTEST_HISTORICAL_DATA_CSV`). This should also be set to `market_data.csv`.
    - Specify the filename for the backtesting results (SR_Proximity column) under the `[DATA]` section (key: `SR_PROXIMITY_OUTPUT_CSV`).
    - Specify the filename for the generated support/resistance levels CSV under the `[DATA]` section (key: `SR_LEVELS_OUTPUT_CSV`).

    **Example `config.ini` structure (assuming `market_data.csv` is in the project root):**
    ```ini
    [BITGET]
    API_KEY = your_actual_api_key
    SECRET_KEY = your_actual_secret_key
    PASSPHRASE = your_actual_passphrase

    [TRADING]
    SYMBOL = BTC/USDT
    TRADE_MARGIN_USDT = 10.0
    LEVERAGE = 5
    # Filename for your historical data CSV for initial S/R in trading_bot.py
    # This file MUST be named market_data.csv and placed in the project root.
    HISTORICAL_DATA_CSV = market_data.csv 

    [DATA]
    # Filename for historical data for backtesting.py
    # This file MUST be named market_data.csv and placed in the project root.
    BACKTEST_HISTORICAL_DATA_CSV = market_data.csv 
    # Filename (or path like results/sr_proximity_data.csv) where backtesting.py will save its SR_Proximity results.
    SR_PROXIMITY_OUTPUT_CSV = sr_proximity_results.csv
    # Filename (or path like results/sr_levels.csv) where support_resistance.py will save calculated S/R levels.
    SR_LEVELS_OUTPUT_CSV = sr_levels.csv
    ```
    **Note:** Ensure `market_data.csv` is present in the project folder before running scripts that depend on it. If you use subfolders for outputs (e.g., `results/file.csv`), ensure the `results/` directory is created.

5.  **Prepare Historical Data**:
    - Place your historical data CSV file, **named `market_data.csv`**, in the main project folder.
    - Ensure `market_data.csv` contains the necessary columns: "Time", "Open", "High", "Low", "Close", "Volume", "Symbol".

## How to Run

### 1. Install Dependencies (One-time setup, if not already done)
- Double-click `install_dependencies.bat` or run it from the command line in the project directory.

### 2. Run Backtest Preliminaries
- This step might involve processing historical data to generate S/R levels or prepare data for the main backtesting module.
- Double-click `run_backtest_preliminaries.bat` or run it from the command line.
- Check the output, which should be a Pandas DataFrame with candle data and S/R proximity information (e.g., `sr_proximity_results.csv`).

### 3. Run the Trading Bot
- Ensure your API keys are configured and you have an internet connection if using real-time data.
- Double-click `run_trading_bot.bat` or run it from the command line.
- The bot will start fetching data, calculating S/R levels (using `market_data.csv` initially as per config), and looking for trading opportunities.

### 4. Generate Support/Resistance Levels CSV (Optional)
- Ensure `market_data.csv` is in the project root and `config.ini` is set up.
- Double-click `generate_sr_levels.bat` or run it from the command line.
- This will create a CSV file (e.g., `sr_levels.csv`) containing the calculated support and resistance levels.

## Key Features
- Support and Resistance (S/R) calculation from historical and real-time data.
- Trading logic based on S/R levels and LHL pattern confirmation.
- Stop-loss and take-profit management.
- Backtesting module to simulate strategy performance.
- Data fetching using the CCXT library for exchanges like Bitget.

## Strategy Overview
1.  **S/R Identification**:
    - Initial S/R levels from historical CSV data (10 most recent S & R).
    - `scipy.signal.argrelextrema` used for identifying swing highs/lows.
    - Real-time S/R updates using polling.
    - S/R levels managed in a Pandas DataFrame.
2.  **Long Entries**:
    - Enter long when price approaches a support level.
    - Stop-loss placed with each entry.
3.  **Trade Management (LHL Pattern)**:
    - If price moves above the midpoint of the prior LHL pattern after entry, switch to take-profit.
    - Otherwise, manage with stop-loss.
    - Take-profit is a percentage decrease from the highest point after LHL confirmation.

## Points of Refinement (from `lhl.txt`)
- Defining "significant" swing lows/highs for S/R.
- Detailed order placement and management logic (CCXT).
- Robust error handling and state management.
- Specifics of closing positions via API. 