import ccxt
import time
import logging
import requests
import hashlib
import hmac
import base64
import json

def _generate_signature(timestamp, method, endpoint, body, secret_key):
    """Generate Bitget API signature - fixed for both GET and POST."""
    if not secret_key:
        raise ValueError("API Secret Key not available for signature generation.")
    try:
        if method == "GET":
            message = timestamp + method + endpoint
            if isinstance(body, dict) and body:
                query_params = sorted(body.items())
                query_string = '&'.join([f"{k}={v}" for k, v in query_params])
                message = message + "?" + query_string
        else: # POST
             # Ensure body is a string for POST signature
             body_str = json.dumps(body) if isinstance(body, dict) else (body if isinstance(body, str) else '')
             message = timestamp + method + endpoint + body_str

        # Create HMAC signature and encode with base64
        signature = base64.b64encode(
            hmac.new(secret_key.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).digest()
        ).decode('utf-8')
        return signature
    except Exception as e:
         logging.error(f"Error generating API signature: {e}", exc_info=True)
         raise # Re-raise exception to halt the operation

def place_uni_long_order(exchange, symbol_ccxt, margin_usdt, leverage, strategy_state, base_url="https://api.bitget.com"):
    """Places a market long order based on margin and leverage, and updates state."""
    leverage_set = False # Flag to track if leverage is confirmed or set

    # --- Check Current Leverage before Setting ---
    try:
        logging.info(f"Fetching current position/leverage info for {symbol_ccxt}...")
        positions = exchange.fetch_positions(symbols=[symbol_ccxt]) 
        current_leverage = None

        if positions: 
            # Find the position matching the symbol 
            matching_position = next((p for p in positions if p.get('info', {}).get('symbol') == symbol_ccxt.replace("/", "").replace(":USDT","")), None)
            if matching_position:
                current_leverage = matching_position.get('leverage')
                logging.info(f"Fetched current leverage for {symbol_ccxt}: {current_leverage}")
            else:
                 logging.info(f"No existing position/leverage found for {symbol_ccxt} in fetch_positions result. Will attempt to set leverage.")
        else:
            logging.info(f"fetch_positions returned empty list or None for {symbol_ccxt}. Will attempt to set leverage.")

        # Compare fetched leverage with desired leverage
        if current_leverage is not None:
            try:
                if float(current_leverage) == float(leverage):
                    logging.info(f"Current leverage ({current_leverage}) already matches desired leverage ({leverage}). Skipping set_leverage call.")
                    leverage_set = True # Consider leverage 'set' as it's already correct
                else:
                    logging.info(f"Current leverage ({current_leverage}) differs from desired ({leverage}). Proceeding to set leverage.")
                    leverage_set = False # Needs to be set
            except ValueError:
                 logging.warning(f"Could not convert fetched leverage '{current_leverage}' to float for comparison. Proceeding to set leverage.")
                 leverage_set = False
        else:
            # Leverage is None (not found), proceed to set
            leverage_set = False

    except (ccxt.NetworkError, ccxt.RequestTimeout) as e:
        logging.warning(f"Network error fetching position/leverage info: {e}. Will attempt to set leverage as fallback.")
        leverage_set = False # Proceed to attempt setting
    except ccxt.NotSupported as e:
         logging.warning(f"Exchange may not support fetch_positions or fetching leverage this way: {e}. Proceeding to set leverage.")
         leverage_set = False
    except Exception as e:
        logging.error(f"Unexpected error fetching position/leverage info: {e}. Proceeding to set leverage.", exc_info=True)
        leverage_set = False # Proceed to attempt setting

    # --- Set Leverage with Retry (Only if needed) ---
    if not leverage_set: 
        logging.info("Attempting to set leverage via API call...")
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logging.info(f"Attempt {attempt + 1}/{max_retries}: Setting leverage to {leverage}x for {symbol_ccxt}...")
                exchange.set_leverage(leverage, symbol_ccxt) 
                logging.info(f"Leverage set to {leverage}x successfully.")
                leverage_set = True
                break # Exit retry loop on success
            except (ccxt.NetworkError, ccxt.RequestTimeout) as e: 
                logging.warning(f"Leverage setting attempt {attempt + 1} failed due to network error: {e}")
                if attempt < max_retries - 1:
                    logging.info("Waiting 5 seconds before retrying leverage setting...")
                    time.sleep(5)
                else:
                    logging.error(f"Failed to set leverage after {max_retries} attempts. Order placement aborted.")
                    # Keep leverage_set as False
            except ccxt.ExchangeError as e: 
                logging.error(f"Exchange error setting leverage: {e}. Order placement aborted.")
                leverage_set = False # Ensure it's false
                break # Don't retry on non-network exchange errors
            except Exception as e: 
                logging.error(f"Unexpected error setting leverage: {e}. Order placement aborted.", exc_info=True)
                leverage_set = False # Ensure it's false
                break # Exit loop on unexpected error

    # Check if leverage was successfully confirmed or set
    if not leverage_set:
        logging.error("Leverage could not be confirmed or set successfully. Aborting order placement.") 
        return None

    # --- Calculate Order Size (If leverage is confirmed/set) --- 
    try: 
        logging.info(f"Attempting to place market long order for {symbol_ccxt} with {margin_usdt} USDT margin...")
        ticker = exchange.fetch_ticker(symbol_ccxt)
        last_price = ticker.get('last')
        if not last_price or last_price <= 0:
            logging.error(f"Could not fetch valid last price ({last_price}) for {symbol_ccxt} to calculate order size.")
            return None

        # Calculate total position value and then the amount of base currency (XRP)
        total_position_value_usdt = margin_usdt * leverage
        xrp_amount = total_position_value_usdt / last_price
        logging.info(f"Margin: {margin_usdt:.2f} USDT, Leverage: {leverage}x, Total Position Value: {total_position_value_usdt:.2f} USDT")
        logging.info(f"Current Price: {last_price}, Calculated XRP Amount: {xrp_amount:.6f}")

        # --- Place the Market Buy Order --- 
        params = {} 
        order = exchange.create_market_buy_order(symbol_ccxt, xrp_amount, params=params)
        logging.info(f"Market long order placement request sent for {symbol_ccxt}.")
        logging.info(f"Order response snippet: {str(order)[:200]}...")

        # --- Update State --- 
        # Get filled amount and entry price, handling potential None values
        filled_amount_raw = order.get('filled') if order else None
        entry_price_raw = order.get('average') if order else None

        # Use calculated/last price as fallback if API doesn't return values
        # Important: Ensure these fallbacks are non-None before formatting
        filled_amount = filled_amount_raw if filled_amount_raw is not None else xrp_amount
        entry_price = entry_price_raw if entry_price_raw is not None else last_price
        
        # Log before updating state, handling None gracefully for logging only
        filled_log = f"{filled_amount:.6f}" if filled_amount is not None else "N/A"
        entry_log = f"{entry_price:.4f}" if entry_price is not None else "N/A"
        logging.info(f"Attempting to update state: in_position=True, size={filled_log}, entry_price={entry_log}")

        # Ensure values are numeric before storing in state, default to 0.0 if None
        final_filled_amount = filled_amount if filled_amount is not None else 0.0
        final_entry_price = entry_price if entry_price is not None else 0.0

        if final_filled_amount > 0: # Only set in_position if we have a size
             strategy_state['in_position'] = True
             strategy_state['position_size'] = final_filled_amount
             strategy_state['entry_price'] = final_entry_price
             logging.info(f"State successfully updated.")
        else:
             strategy_state['in_position'] = False # Ensure state remains False if size is 0
             strategy_state['position_size'] = 0.0
             strategy_state['entry_price'] = 0.0
             logging.warning("Order placed but filled amount is zero or unavailable. State NOT updated to in_position=True.")

        return order

    except ccxt.InsufficientFunds as e:
        # This might trigger if 4 USDT isn't enough margin for the minimum order size after leverage
        logging.error(f"Insufficient funds (margin) to place order: {e}")
    except ccxt.ExchangeError as e:
        logging.error(f"Bitget Exchange Error placing order: {e}")
    except Exception as e:
        logging.error(f"Unexpected error placing order: {e}", exc_info=True)
        # Ensure state is not incorrectly set if order fails critically before sending
        strategy_state['in_position'] = False
        strategy_state['position_size'] = 0.0
        strategy_state['entry_price'] = 0.0
    return None

def close_uni_long_order(symbol_bitget, api_credentials, strategy_state, margin_coin="USDT", base_url="https://api.bitget.com"):
    """Closes the existing long position using a direct V1 API call."""
    if not strategy_state['in_position'] or strategy_state['position_size'] <= 0:
        logging.warning("Close order requested but not in a position or size is zero.")
        return None

    # Ensure credentials are loaded
    if not api_credentials:
         logging.error("API credentials not loaded. Cannot place closing order.")
         return None

    api_key = api_credentials.get('API_KEY')
    secret_key = api_credentials.get('SECRET_KEY')
    passphrase = api_credentials.get('PASSPHRASE')

    if not all([api_key, secret_key, passphrase]):
        logging.error("Missing one or more API credentials (Key, Secret, Passphrase). Cannot close order.")
        return None

    try:
        position_size_float = strategy_state['position_size']
        # Convert position size to string for the API, ensuring appropriate precision
        # Bitget might require specific decimal places - check API docs if errors occur
        position_size_str = "{:.8f}".format(position_size_float).rstrip('0').rstrip('.') # Format and remove trailing zeros/dot

        logging.info(f"Attempting to close long position for {symbol_bitget} with size {position_size_str} via V1 API...")

        endpoint = "/api/mix/v1/order/placeOrder"
        method = "POST"
        timestamp = str(int(time.time() * 1000))

        params = {
            "symbol": symbol_bitget,
            "marginCoin": margin_coin,
            "size": position_size_str,
            "side": "close_long", # Explicitly close long
            "orderType": "market",
            # "timeInForce": "normal" # Optional, defaults likely okay for market
        }

        signature = _generate_signature(timestamp, method, endpoint, params, secret_key)

        headers = {
            "Content-Type": "application/json",
            "ACCESS-KEY": api_key,
            "ACCESS-SIGN": signature,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-PASSPHRASE": passphrase,
            "locale": "en-US" # Often recommended
        }

        # Use requests to make the API call
        response = requests.post(
            base_url + endpoint,
            headers=headers,
            json=params # Send params as JSON body
        )
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        response_data = response.json()

        logging.info(f"Close order API Response: {response_data}")

        # Check Bitget API response code (V1 sometimes uses "0", but log shows "00000" used here)
        if response_data.get("code") == "00000": # Check for "00000" instead of "0"
            logging.info(f"API confirmed close order placed successfully for {symbol_bitget}.")
            # Update state
            logging.info(f"Updating state: Closing position.")
            strategy_state['in_position'] = False
            strategy_state['position_size'] = 0.0
            strategy_state['entry_price'] = 0.0
            return response_data # Return success response
        else:
            # Log specific API error
            error_msg = response_data.get("msg", "No error message from API.")
            logging.error(f"Bitget API Error closing position (Code: {response_data.get('code')}): {error_msg}")
            # Consider re-checking position state here if the error is ambiguous
            return None

    except requests.exceptions.RequestException as e:
         logging.error(f"Network Error closing position via requests: {e}")
    except Exception as e:
        logging.error(f"Unexpected error closing position via V1 API: {e}", exc_info=True) 