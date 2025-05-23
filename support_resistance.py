import pandas as pd
from scipy.signal import argrelextrema
import numpy as np
import configparser
import os
import logging

# Attempt to import data_fetcher; will be used for loading CSV
# This might require ensuring data_fetcher.py is in PYTHONPATH or same directory
try:
    import data_fetcher
except ImportError:
    print("Error: data_fetcher.py not found. Ensure it's in the same directory or PYTHONPATH.")
    data_fetcher = None

# --- Load Configuration ---
config = configparser.ConfigParser()
config_file_path = 'config.ini'
if os.path.exists(config_file_path):
    config.read(config_file_path)
else:
    print(f"Error: Configuration file '{config_file_path}' not found. Please create one.")
    # Exit or use sensible defaults if config is critical
    exit()

# Get paths and parameters from config, with fallbacks
# Correctly reading from [TRADING] and [DATA] sections as per your config.ini
INPUT_CSV_PATH = config.get('TRADING', 'HISTORICAL_DATA_CSV', fallback='market_data.csv')
SR_LEVELS_OUTPUT_CSV_PATH = config.get('DATA', 'SR_LEVELS_OUTPUT_CSV', fallback='sr_levels.csv')

# New parameter for LHL pattern tolerance
SR_PRICE_TOLERANCE_PERCENT = float(config.get('TRADING', 'SR_PRICE_TOLERANCE_PERCENT', fallback='0.005'))


def find_lhl_support_resistance(data_df, tolerance_percent=0.01, window_size=5, sr_count=10):
    """
    Identifies LHL (Low-High-Low) patterns for support and Resistance based on Close prices.
    Support is formed by two lows at similar price levels, with the peak between them forming resistance.
    
    Strategy:
    1. First looks for patterns near current price to handle transitions
    2. Then looks for recent patterns (last 50 candles)
    3. Finally falls back to historical patterns
    4. Merges support/resistance levels that are very close to each other
    5. Prioritizes proximity to current price, then recency

    Args:
        data_df (pd.DataFrame): DataFrame with 'Close' prices and 'timestamp' column
        tolerance_percent (float): Percentage tolerance for determining if two lows are at 'same' price.
        window_size (int): The 'order' parameter for scipy.signal.argrelextrema.
        sr_count (int): The maximum number of top support and resistance levels to return.

    Returns:
        pd.DataFrame: DataFrame containing identified Support and Resistance levels with 'Type', 'Tier', 'Price', 'Timestamp'.
    """
    if data_df.empty or 'Close' not in data_df.columns or 'timestamp' not in data_df.columns:
        print("DataFrame is empty or required columns ('Close', 'timestamp') are missing.")
        return pd.DataFrame()

    logging.debug("Starting S/R level calculation...")

    # Find local minima and maxima
    minima_indices = argrelextrema(data_df['Close'].values, np.less_equal, order=window_size)[0]
    maxima_indices = argrelextrema(data_df['Close'].values, np.greater_equal, order=window_size)[0]
    current_price = data_df['Close'].iloc[-1]

    all_extrema = sorted(np.concatenate((minima_indices, maxima_indices)))
    found_patterns = []

    # Iterate through all extrema to find LHL patterns
    for i in range(len(all_extrema) - 2):
        idx0 = all_extrema[i]
        idx1 = all_extrema[i+1]
        idx2 = all_extrema[i+2]

        is_l0 = idx0 in minima_indices
        is_h1 = idx1 in maxima_indices
        is_l2 = idx2 in minima_indices

        if is_l0 and is_h1 and is_l2:
            close0 = data_df['Close'].iloc[idx0]
            close1 = data_df['Close'].iloc[idx1]
            close2 = data_df['Close'].iloc[idx2]
            timestamp = data_df['timestamp'].iloc[idx2]

            if close1 > close0 and close1 > close2:
                max_allowed_diff = max(close0, close2) * tolerance_percent
                if abs(close0 - close2) <= max_allowed_diff:
                    avg_low_price = (close0 + close2) / 2
                    found_patterns.append({
                        'support_price': avg_low_price,
                        'resistance_price': close1,
                        'timestamp': timestamp,
                        'recency_index': idx2,
                        'distance': abs(avg_low_price - current_price)
                    })

    if not found_patterns:
        return pd.DataFrame()

    # Group patterns by proximity to merge similar levels
    def group_patterns_by_price(patterns, ref_price_key='support_price'):
        if not patterns:
            return []
            
        patterns = sorted(patterns, key=lambda x: x[ref_price_key])
        groups = []
        current_group = [patterns[0]]
        
        for pattern in patterns[1:]:
            last_pattern = current_group[-1]
            price_diff = abs(pattern[ref_price_key] - last_pattern[ref_price_key])
            price_tolerance = last_pattern[ref_price_key] * tolerance_percent * 2
            
            if price_diff <= price_tolerance:
                current_group.append(pattern)
            else:
                # When starting a new group, select the most relevant pattern from current group
                merged = select_representative_pattern(current_group)
                groups.append(merged)
                current_group = [pattern]
        
        # Don't forget the last group
        if current_group:
            merged = select_representative_pattern(current_group)
            groups.append(merged)
        
        return groups

    def select_representative_pattern(patterns):
        if not patterns:
            return None
        
        # Sort by distance to current price, then by recency
        patterns.sort(key=lambda x: (x['distance'], -x['recency_index']))
        
        # Take the most relevant pattern's price but keep track of all timestamps
        selected = patterns[0].copy()
        selected['all_timestamps'] = [p['timestamp'] for p in patterns]
        selected['pattern_count'] = len(patterns)
        
        return selected

    # First look for patterns close to current price
    close_patterns = [p for p in found_patterns 
                     if abs(p['support_price'] - current_price) <= current_price * tolerance_percent * 3]
    
    # Then look for recent patterns
    recent_patterns = [p for p in found_patterns if p['recency_index'] >= len(data_df) - 50]

    # Choose the most relevant pattern for S1
    if close_patterns:
        close_patterns = group_patterns_by_price(close_patterns)
        close_patterns.sort(key=lambda x: x['distance'])
        most_recent_pattern = close_patterns[0]
        logging.info(f"Using nearby pattern as S1: Support={most_recent_pattern['support_price']:.4f}")
    elif recent_patterns:
        recent_patterns = group_patterns_by_price(recent_patterns)
        recent_patterns.sort(key=lambda x: x['recency_index'], reverse=True)
        most_recent_pattern = recent_patterns[0]
        logging.info(f"Using recent pattern as S1: Support={most_recent_pattern['support_price']:.4f}")
    else:
        found_patterns = group_patterns_by_price(found_patterns)
        found_patterns.sort(key=lambda x: x['recency_index'], reverse=True)
        most_recent_pattern = found_patterns[0]
        logging.info(f"Using historical pattern as S1: Support={most_recent_pattern['support_price']:.4f}")

    s1_price = most_recent_pattern['support_price']
    r1_price = most_recent_pattern['resistance_price']
    s1_timestamp = most_recent_pattern['timestamp']

    # Collect other levels
    other_supports = []
    other_resistances = []

    # Group remaining patterns
    remaining_patterns = [p for p in found_patterns if abs(p['support_price'] - s1_price) > s1_price * tolerance_percent * 2]
    grouped_patterns = group_patterns_by_price(remaining_patterns)

    for pattern in grouped_patterns:
        if pattern['support_price'] < s1_price:  # Only include supports below S1
            other_supports.append({
                'price': pattern['support_price'],
                'timestamp': pattern['timestamp'],
                'pattern_count': pattern.get('pattern_count', 1)
            })
        if pattern['resistance_price'] > r1_price and pattern['resistance_price'] > s1_price:
            other_resistances.append({
                'price': pattern['resistance_price'],
                'timestamp': pattern['timestamp'],
                'pattern_count': pattern.get('pattern_count', 1)
            })

    # Sort by price and strength (pattern count)
    other_supports.sort(key=lambda x: (-x['pattern_count'], -x['price']))
    other_resistances.sort(key=lambda x: (x['price'], -x['pattern_count']))

    final_sr_levels = []
    
    # Add S1
    final_sr_levels.append({
        'Type': 'Support',
        'Tier': 'S1',
        'Price': s1_price,
        'Timestamp': s1_timestamp
    })
    
    # Add other supports
    for i, support in enumerate(other_supports[:sr_count-1], start=2):
        logging.debug(f"Adding S{i}: Support={support['price']:.4f} (Count: {support['pattern_count']})")
        final_sr_levels.append({
            'Type': 'Support',
            'Tier': f'S{i}',
            'Price': support['price'],
            'Timestamp': support['timestamp']
        })
    
    # Add R1
    final_sr_levels.append({
        'Type': 'Resistance',
        'Tier': 'R1',
        'Price': r1_price,
        'Timestamp': s1_timestamp
    })
    
    # Add other resistances
    for i, resistance in enumerate(other_resistances[:sr_count-1], start=2):
        logging.debug(f"Adding R{i}: Resistance={resistance['price']:.4f} (Count: {resistance['pattern_count']})")
        final_sr_levels.append({
            'Type': 'Resistance',
            'Tier': f'R{i}',
            'Price': resistance['price'],
            'Timestamp': resistance['timestamp']
        })

    # Create final DataFrame
    sr_df = pd.DataFrame(final_sr_levels)
    
    if not sr_df.empty:
        sr_df['TierNum'] = sr_df['Tier'].str[1:].astype(int)
        sr_df = sr_df.sort_values(by=['Type', 'TierNum'], ascending=[False, True])
        sr_df = sr_df.drop(columns=['TierNum'])
        sr_df = sr_df.reset_index(drop=True)

    logging.info(f"Final S/R levels: {len(sr_df)} levels identified")
    return sr_df


def main():
    print(f"--- S/R Level Generation Script (LHL Pattern) ---")
    print(f"Attempting to load candlestick data from: {INPUT_CSV_PATH}")

    market_candles_df = None
    if data_fetcher:
        try:
            market_candles_df = data_fetcher.load_market_data_from_csv(INPUT_CSV_PATH)
        except Exception as e:
            print(f"Error loading market data using data_fetcher: {e}")
            market_candles_df = None
    
    if market_candles_df is None or market_candles_df.empty:
        print("Falling back to direct pandas CSV load (ensure 'Close' column exists).")
        try:
            market_candles_df = pd.read_csv(INPUT_CSV_PATH)
            
            # Rename columns to match expected format
            column_mapping = {
                'close': 'Close',
                'Close': 'Close',
                'time': 'timestamp',
                'Time': 'timestamp',
                'date': 'timestamp',
                'datetime': 'timestamp'
            }
            for old_col, new_col in column_mapping.items():
                if old_col in market_candles_df.columns:
                    market_candles_df.rename(columns={old_col: new_col}, inplace=True)
            
            # If timestamp column doesn't exist, use the second column as timestamp
            if 'timestamp' not in market_candles_df.columns and len(market_candles_df.columns) > 1:
                try:
                    market_candles_df['timestamp'] = pd.to_datetime(market_candles_df.iloc[:, 1])
                except Exception as e:
                    print(f"Warning: Could not create timestamp column from data: {e}")
            else:
                # If timestamp column exists, ensure it's in datetime format
                try:
                    market_candles_df['timestamp'] = pd.to_datetime(market_candles_df['timestamp'])
                except Exception as e:
                    print(f"Warning: Could not parse timestamp column as datetime: {e}")
            
            if 'Close' not in market_candles_df.columns:
                print("Error: 'Close' column not found in the loaded CSV. Cannot proceed.")
                market_candles_df = pd.DataFrame()
        except FileNotFoundError:
            print(f"Error: Input CSV file '{INPUT_CSV_PATH}' not found. Please ensure it exists.")
            market_candles_df = pd.DataFrame()
        except Exception as e:
            print(f"Error directly loading market data with pandas: {e}")
            market_candles_df = pd.DataFrame()

    if market_candles_df.empty:
        print(f"No market data loaded. Please ensure '{INPUT_CSV_PATH}' exists, is correctly named in config.ini, and contains valid candlestick data with a 'Close' column.")
    else:
        print(f"Loaded {len(market_candles_df)} records from {INPUT_CSV_PATH}.")
        print("Columns in DataFrame:", market_candles_df.columns.tolist())
        
        sr_levels_df = find_lhl_support_resistance(
            market_candles_df,
            tolerance_percent=SR_PRICE_TOLERANCE_PERCENT,
            window_size=10,
            sr_count=10
        )

        if not sr_levels_df.empty:
            print(f"\nCalculated S/R Levels (Top {len(sr_levels_df)} shown):")
            print(sr_levels_df)
            try:
                output_dir = os.path.dirname(SR_LEVELS_OUTPUT_CSV_PATH)
                if output_dir and not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                    print(f"Created directory: {output_dir}")
                sr_levels_df.to_csv(SR_LEVELS_OUTPUT_CSV_PATH, index=False)
                print(f"\nS/R levels saved to: {SR_LEVELS_OUTPUT_CSV_PATH}")
            except Exception as e:
                print(f"\nError saving S/R levels to CSV: {e}")
        else:
            print("\nNo S/R levels identified based on LHL pattern.")

if __name__ == "__main__":
    main()
