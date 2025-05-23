import pandas as pd
import ccxt
import configparser
import time
import logging
import os
import traceback
from datetime import datetime
from data_fetcher import load_market_data_from_csv
from support_resistance import find_lhl_support_resistance

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s\n%(pathname)s:%(lineno)d',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

def load_config():
    """Load configuration from config.ini"""
    try:
        config = configparser.ConfigParser()
        if not os.path.exists('config.ini'):
            raise FileNotFoundError("config.ini not found")
        config.read('config.ini')
        
        # Validate required sections and keys
        required_sections = ['BITGET', 'TRADING']
        for section in required_sections:
            if section not in config:
                raise ValueError(f"Missing required section [{section}] in config.ini")
        
        required_keys = {
            'BITGET': ['API_KEY', 'SECRET_KEY', 'PASSPHRASE'],
            'TRADING': ['SYMBOL', 'TRADE_MARGIN_USDT', 'LEVERAGE', 'SR_PRICE_TOLERANCE_PERCENT', 'ENTRY_PROXIMITY_PERCENT']
        }
        
        for section, keys in required_keys.items():
            for key in keys:
                if not config.has_option(section, key):
                    raise ValueError(f"Missing required key {key} in section [{section}]")
        
        return {
            'api_key': config.get('BITGET', 'API_KEY'),
            'secret_key': config.get('BITGET', 'SECRET_KEY'),
            'passphrase': config.get('BITGET', 'PASSPHRASE'),
            'symbol': config.get('TRADING', 'SYMBOL'),
            'trade_margin_usdt': float(config.get('TRADING', 'TRADE_MARGIN_USDT')),
            'leverage': int(config.get('TRADING', 'LEVERAGE')),
            'sr_price_tolerance': float(config.get('TRADING', 'SR_PRICE_TOLERANCE_PERCENT')),
            'entry_proximity': float(config.get('TRADING', 'ENTRY_PROXIMITY_PERCENT')),
            'historical_data_csv': config.get('TRADING', 'HISTORICAL_DATA_CSV')
        }
    except Exception as e:
        logging.error(f"Error loading config: {str(e)}\n{traceback.format_exc()}")
        raise

def setup_exchange(api_key, secret_key, passphrase):
    """Initialize the Bitget exchange client"""
    try:
        exchange = ccxt.bitget({
            'apiKey': api_key,
            'secret': secret_key,
            'password': passphrase,
            'defaultType': 'swap'
        })
        exchange.load_markets()
        return exchange
    except Exception as e:
        logging.error(f"Failed to initialize exchange: {e}")
        return None

def fetch_initial_data(exchange, symbol, limit=1000):
    """Fetch initial historical OHLCV data"""
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, '5m', limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        logging.error(f"Error fetching initial data: {e}")
        return pd.DataFrame()

def calculate_stop_loss_price(entry_price, margin_usdt, leverage):
    """Calculate stop loss price that would result in 1.5 USDT loss"""
    target_loss_usdt = 1.5
    position_size = (margin_usdt * leverage) / entry_price
    price_move_for_loss = target_loss_usdt / position_size
    return entry_price - price_move_for_loss

def is_developing_lhl(current_price, sr_df, entry_proximity_percent):
    """Check if there's a developing LHL pattern near current price"""
    if sr_df is None or sr_df.empty:
        return False, None
    
    # Get all support levels
    supports = sr_df[sr_df['Type'] == 'Support']
    if supports.empty:
        return False, None

    # Look through all support levels
    for _, support_row in supports.iterrows():
        try:
            support_price = float(support_row['Price'])
            allowed_distance = support_price * entry_proximity_percent
            
            # Only trigger if price is approaching from above
            if current_price > support_price and abs(current_price - support_price) <= allowed_distance:
                return True, support_price
        except (ValueError, TypeError):
            continue
            
    return False, None

def get_closest_sr_levels(current_price, historical_candles_df, config):
    """Calculate S/R levels focusing on the 10 most recent support levels and selecting the nearest as S1"""
    # Use more candles to catch more potential support levels
    recent_data = historical_candles_df.tail(1000)  # Use last 1000 candles for better context
    
    logging.debug(f"Calculating S/R levels for current price: {current_price:.4f}")
    
    # Calculate S/R levels
    sr_df = find_lhl_support_resistance(
        recent_data,
        tolerance_percent=config['sr_price_tolerance'],
        window_size=20,
        sr_count=20  # Get more levels to ensure we have enough supports
    )
    
    if sr_df.empty:
        logging.debug("No S/R levels found")
        return pd.DataFrame(columns=['Type', 'Tier', 'Price', 'Timestamp', 'distance'])
    
    # Split into supports and resistances
    supports = sr_df[sr_df['Type'] == 'Support'].copy()
    resistances = sr_df[sr_df['Type'] == 'Resistance'].copy()
    
    # Process support levels
    if not supports.empty:
        # Sort supports by timestamp (most recent first) and take the last 10
        supports = supports.sort_values('Timestamp', ascending=False).head(10)
        
        # Calculate distance to current price
        supports['distance'] = abs(supports['Price'] - current_price)
        
        # Sort by distance to get the nearest support
        supports = supports.sort_values('distance')
        
        # Assign new tiers based on distance (nearest = S1)
        supports['Tier'] = [f'S{i+1}' for i in range(len(supports))]
        
        # Log support level details
        support_details = []
        for _, row in supports.iterrows():
            support_details.append(f"{row['Tier']}={row['Price']:.4f}")
        logging.info(f"Support levels found: {', '.join(support_details)}")
        
        # Check if price is near the nearest support (S1)
        if not supports.empty:
            s1 = supports.iloc[0]
            support_proximity = abs(current_price - s1['Price']) / s1['Price']
            if support_proximity <= config['sr_price_tolerance']:
                logging.info(f"Price {current_price:.4f} is near support {s1['Price']:.4f} ({s1['Tier']})")
    
    # Process resistance levels
    if not resistances.empty:
        # Sort resistances by timestamp (most recent first) and take the last 10
        resistances = resistances.sort_values('Timestamp', ascending=False).head(10)
        
        # Calculate distance to current price
        resistances['distance'] = abs(resistances['Price'] - current_price)
        
        # Sort by distance to get the nearest resistance
        resistances = resistances.sort_values('distance')
        
        # Assign new tiers based on distance (nearest = R1)
        resistances['Tier'] = [f'R{i+1}' for i in range(len(resistances))]
        
        # Log resistance level details
        resistance_details = []
        for _, row in resistances.iterrows():
            resistance_details.append(f"{row['Tier']}={row['Price']:.4f}")
        if resistance_details:
            logging.info(f"Resistance levels found: {', '.join(resistance_details)}")
    
    # Combine levels and maintain proper ordering
    sr_df = pd.concat([supports, resistances])
    
    # Final sorting and cleanup
    if not sr_df.empty:
        sr_df = sr_df.sort_values(['Type', 'distance'])
        sr_df = sr_df.reset_index(drop=True)
    
    return sr_df

def fetch_with_retry(exchange, symbol, retries=3, delay=2):
    """Fetch data with retry mechanism"""
    for attempt in range(retries):
        try:
            candles = exchange.fetch_ohlcv(symbol, '5m', limit=2)
            if candles:
                return candles
        except Exception as e:
            if attempt < retries - 1:  # If not the last attempt
                logging.warning(f"Fetch attempt {attempt + 1} failed: {str(e)}. Retrying in {delay} seconds...")
                time.sleep(delay)
                continue
            else:
                raise  # Re-raise the last exception if all retries failed
    return None

def safe_get_float_from_df(df, index, column):
    """Safely extract a float value from a DataFrame"""
    if df is None or df.empty or index >= len(df):
        return None
    try:
        value = df.iloc[index][column]
        return float(value) if pd.notnull(value) else None
    except (IndexError, ValueError, TypeError):
        return None

def main():
    try:
        logging.info("Starting LHL Pattern Trading Bot...")
        
        # Load configuration
        config = load_config()
        logging.info(f"Configuration loaded successfully for symbol {config['symbol']}")
        
        # Initialize exchange
        exchange = setup_exchange(config['api_key'], config['secret_key'], config['passphrase'])
        if not exchange:
            raise Exception("Failed to initialize exchange")
        
        # Initialize bot state
        historical_candles_df = fetch_initial_data(exchange, config['symbol'])
        if historical_candles_df.empty:
            raise Exception("Failed to fetch initial historical data")
        
        # Bot state variables
        is_in_position = False
        last_entry_price = None
        highest_price_since_entry = None
        current_lhl_resistance_target = None
        calculated_stop_loss_price = None
        
        logging.info("Bot initialized successfully, entering main loop...")
        
        # Main polling loop
        while True:
            try:
                # 1. Fetch latest candle with retry mechanism
                latest_candles = fetch_with_retry(exchange, config['symbol'])
                if not latest_candles:
                    logging.error("Failed to fetch data after retries, waiting for next cycle...")
                    time.sleep(30)
                    continue
                
                latest_df = pd.DataFrame(latest_candles, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
                latest_df['timestamp'] = pd.to_datetime(latest_df['timestamp'], unit='ms')
                
                # 2. Update historical data
                historical_candles_df = pd.concat([historical_candles_df, latest_df])\
                    .drop_duplicates(subset=['timestamp'])\
                    .sort_values('timestamp')
                
                # Keep only the last 1000 candles to maintain performance
                historical_candles_df = historical_candles_df.tail(1000).reset_index(drop=True)
                
                # 3. Get current price and calculate S/R levels
                current_price = float(latest_df.iloc[-1]['Close'])
                sr_df = get_closest_sr_levels(current_price, historical_candles_df, config)
                
                # 4. Signal Detection & Management
                if not is_in_position:
                    # Check for entry signal
                    has_lhl_pattern, support_price = is_developing_lhl(
                        current_price, 
                        sr_df, 
                        config['entry_proximity']
                    )
                    
                    if has_lhl_pattern:
                        is_in_position = True
                        last_entry_price = current_price
                        highest_price_since_entry = current_price
                        
                        # Set resistance target to R1 from current S/R calculation
                        r1_level = sr_df[sr_df['Tier'] == 'R1']
                        if not r1_level.empty:
                            current_lhl_resistance_target = float(r1_level.iloc[0]['Price'])
                        
                        calculated_stop_loss_price = calculate_stop_loss_price(
                            last_entry_price,
                            config['trade_margin_usdt'],
                            config['leverage']
                        )
                        
                        logging.info(
                            f"ENTRY SIGNAL: Price={current_price}, Support={support_price}, "
                            f"Stop Loss={calculated_stop_loss_price}, Target={current_lhl_resistance_target}"
                        )
                
                else:  # In position
                    # Update highest price since entry
                    highest_price_since_entry = max(highest_price_since_entry, current_price)
                    
                    # Check stop loss
                    if current_price <= calculated_stop_loss_price:
                        logging.info(
                            f"STOP LOSS: Entry={last_entry_price}, Exit={current_price}, "
                            f"Loss={calculated_stop_loss_price - last_entry_price}"
                        )
                        is_in_position = False
                        last_entry_price = None
                        highest_price_since_entry = None
                        current_lhl_resistance_target = None
                        calculated_stop_loss_price = None
                    
                    # Check take profit (if we're still in position and above stop loss)
                    elif current_price > last_entry_price:
                        gain_distance = highest_price_since_entry - last_entry_price
                        take_profit_trigger = highest_price_since_entry - (0.15 * gain_distance)
                        
                        if current_price <= take_profit_trigger:
                            logging.info(
                                f"TAKE PROFIT: Entry={last_entry_price}, Exit={current_price}, "
                                f"Highest={highest_price_since_entry}, Profit={current_price - last_entry_price}"
                            )
                            is_in_position = False
                            last_entry_price = None
                            highest_price_since_entry = None
                            current_lhl_resistance_target = None
                            calculated_stop_loss_price = None
                
                # Get current S/R levels
                current_s1 = sr_df[sr_df['Tier'] == 'S1'].iloc[0]['Price'] if not sr_df.empty else 'N/A'
                current_r1 = sr_df[sr_df['Tier'] == 'R1'].iloc[0]['Price'] if not sr_df.empty else 'N/A'
                
                # Store previous S/R levels for comparison
                if not hasattr(main, 'prev_s1'):
                    main.prev_s1 = current_s1
                    main.prev_r1 = current_r1
                
                # Log current state with S/R level changes
                if current_s1 != main.prev_s1 or current_r1 != main.prev_r1:
                    logging.info(
                        f"S/R UPDATE - Current Price: {current_price}, "
                        f"Position: {'Yes' if is_in_position else 'No'}, "
                        f"S1: {main.prev_s1}->{current_s1}, "
                        f"R1: {main.prev_r1}->{current_r1}"
                    )
                    main.prev_s1 = current_s1
                    main.prev_r1 = current_r1
                else:
                    logging.info(
                        f"Current Price: {current_price}, "
                        f"Position: {'Yes' if is_in_position else 'No'}, "
                        f"S1: {current_s1}, R1: {current_r1}"
                    )
                
                # Sleep for 30 seconds
                time.sleep(30)
                
            except Exception as e:
                logging.error(f"Error in main loop: {str(e)}\n{traceback.format_exc()}")
                time.sleep(30)  # Still sleep on error to prevent rapid retries
    
    except KeyboardInterrupt:
        logging.info("Bot shutdown requested by user...")
    except Exception as e:
        logging.error(f"Critical error: {str(e)}\n{traceback.format_exc()}")
    finally:
        logging.info("Bot shutting down...")

if __name__ == "__main__":
    main()
