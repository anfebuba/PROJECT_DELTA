# data_fetcher.py
"""
Enhanced data fetcher for LHL Trading Bot
- Fetches historical/real-time data from Bitget
- Saves to specified output directory
- Handles both CSV and API data sources
"""

import pandas as pd
import ccxt
import logging
import argparse
from pathlib import Path
import os
import configparser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data_fetch.log'),
        logging.StreamHandler()
    ]
)

DEFAULT_COLUMNS = ["Time", "Open", "High", "Low", "Close", "Volume", "Symbol"]

# Load configuration
_config = configparser.ConfigParser()
_config.read('config.ini')

def get_exchange_client(exchange_id='bitget'):
    """Initialize CCXT exchange client with credentials from config.ini"""
    try:
        exchange = getattr(ccxt, exchange_id)({
            'apiKey': _config.get('BITGET', 'API_KEY', fallback=''),
            'secret': _config.get('BITGET', 'SECRET_KEY', fallback=''),
            'password': _config.get('BITGET', 'PASSPHRASE', fallback=''),
            'options': {'defaultType': 'swap'}
        })
        exchange.load_markets()
        return exchange
    except Exception as e:
        logging.error(f"Exchange initialization failed: {str(e)}")
        return None

def fetch_ohlcv_data(exchange, symbol='BTC/USDT', timeframe='5m', limit=1000):
    """Fetch OHLCV data from exchange"""
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        # Create DataFrame with proper column names
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # Convert timestamp to datetime
        df['Time'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Rename columns to match expected format
        df = df.rename(columns={
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume'
        })
        
        # Add symbol column
        df['Symbol'] = symbol
        
        # Select and reorder columns to match DEFAULT_COLUMNS
        df = df[DEFAULT_COLUMNS]
        
        return df
    except Exception as e:
        logging.error(f"Data fetch failed: {str(e)}")
        return None

def save_data(df, output_path):
    """Save data to specified path"""
    try:
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        logging.info(f"Data saved to {output_path}")
        return True
    except Exception as e:
        logging.error(f"Failed to save data: {str(e)}")
        return False

def load_market_data_from_csv(file_path):
    """
    Load market data from a CSV file, ensuring proper column names and timestamp formatting.
    
    Args:
        file_path (str): Path to the CSV file containing market data.
        
    Returns:
        pd.DataFrame: DataFrame with properly formatted columns or empty DataFrame on error.
    """
    try:
        # Read the CSV file
        df = pd.read_csv(file_path)
        
        # Create a mapping of possible column names to standardized names
        column_mapping = {
            'close': 'Close',
            'time': 'timestamp',
            'Time': 'timestamp',
            'date': 'timestamp',
            'datetime': 'timestamp'
        }
        
        # Rename columns if they exist
        for old_col, new_col in column_mapping.items():
            if old_col in df.columns:
                df.rename(columns={old_col: new_col}, inplace=True)
        
        # If timestamp column doesn't exist and we have at least 2 columns,
        # assume the second column is the timestamp
        if 'timestamp' not in df.columns and len(df.columns) > 1:
            try:
                df['timestamp'] = pd.to_datetime(df.iloc[:, 1])
            except Exception as e:
                logging.warning(f"Could not create timestamp column from second column: {e}")
        
        # Convert timestamp to datetime if it exists
        if 'timestamp' in df.columns:
            try:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            except Exception as e:
                logging.warning(f"Could not convert timestamp column to datetime: {e}")
                if 'timestamp' not in df.columns:
                    df['timestamp'] = None
        
        # Verify 'Close' column exists
        if 'Close' not in df.columns:
            logging.error("'Close' column not found in CSV data")
            return pd.DataFrame()
            
        return df
        
    except Exception as e:
        logging.error(f"Error loading market data from CSV: {e}")
        return pd.DataFrame()

def main():
    parser = argparse.ArgumentParser(description='Fetch market data for LHL Trading Bot')
    parser.add_argument('--output', required=True, help='Output CSV file path')
    parser.add_argument('--symbol', default='BTC/USDT', help='Trading symbol')
    parser.add_argument('--timeframe', default='5m', help='OHLCV timeframe')
    parser.add_argument('--limit', type=int, default=1000, help='Number of candles to fetch')
    args = parser.parse_args()

    logging.info(f"Starting data fetch for {args.symbol} ({args.timeframe})")
    
    # Fetch from exchange
    exchange = get_exchange_client()
    if not exchange:
        return

    df = fetch_ohlcv_data(exchange, args.symbol, args.timeframe, args.limit)
    if df is not None:
        if save_data(df, args.output):
            print(f"\nLast 5 records:\n{df.tail()}")
        else:
            logging.error("Data save failed")
    else:
        logging.error("No data received from exchange")

if __name__ == '__main__':
    main()