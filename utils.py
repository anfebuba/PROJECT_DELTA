# utils.py

"""
Utility functions shared across the LHL trading bot project.

Potential functions based on lhl.txt:
- CCXT exchange client initialization (might be better in data_fetcher.py if specific to data).
- Setting leverage (CCXT).
- Placing long orders (CCXT, create_market_buy_order).
- Closing long positions (Bitget V1 API call if CCXT direct close is not preferred or different).
- API signature generation (for direct API calls like Bitget V1).
- Error handling wrappers or specific error types.
- Logging configuration (if centralized).
- Symbol conversion utilities (e.g. Bitget specific to standard).
"""

import ccxt
import logging
import hashlib
import hmac
import time
import json
import requests # For direct API calls if needed

# Configure logging (can be centralized here or done in each main script)
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- CCXT Related Utilities (some might overlap/move to data_fetcher.py) ---

def get_ccxt_exchange(exchange_id, api_key, api_secret, passphrase=None, is_sandbox=False):
    """
    DEPRECATED: Initializes and returns a CCXT exchange instance.
    Moved most of this logic to data_fetcher.get_exchange_client which also handles config fallbacks.
    This function is kept for now to avoid breaking existing calls but should be phased out.
    Use data_fetcher.get_exchange_client(api_key, api_secret, passphrase, exchange_id) instead,
    passing the credentials explicitly.
    """
    logging.warning("utils.get_ccxt_exchange is DEPRECATED. Use data_fetcher.get_exchange_client and pass credentials directly.")
    try:
        exchange_class = getattr(ccxt, exchange_id)
        config = {
            'apiKey': api_key,
            'secret': api_secret,
        }
        if passphrase:
            config['password'] = passphrase
        
        exchange = exchange_class(config)
        if is_sandbox and hasattr(exchange, 'set_sandbox_mode'):
            exchange.set_sandbox_mode(True)
            logging.info(f"Sandbox mode enabled for {exchange_id}")
        # exchange.options['defaultType'] = 'swap' # if trading perpetual futures
        return exchange
    except Exception as e:
        logging.error(f"Error initializing CCXT exchange {exchange_id}: {e}")
        return None

def set_leverage_with_retry(exchange, symbol, leverage, max_retries=3, delay_seconds=5):
    """
    Sets leverage for a symbol on the exchange, with retry logic.
    Assumes the symbol is for a futures/margin market that supports leverage.
    """
    if not hasattr(exchange, 'set_leverage') or not exchange.has.get('setLeverage'):
        logging.warning(f"{exchange.id} does not support setting leverage via CCXT, or flag not set.")
        # Check if the market itself supports leverage according to CCXT market structure
        try:
            exchange.load_markets()
            market = exchange.market(symbol)
            if not market.get('contract', False): # or market.get('type') not in ['future', 'swap']
                logging.warning(f"Symbol {symbol} on {exchange.id} may not be a leverageable market type ({market.get('type')})")
                # return False # Or let it try and fail if API supports it anyway
        except Exception as e:
            logging.warning(f"Could not check market details for {symbol} on {exchange.id}: {e}")
            # Proceed with trying to set leverage cautiously

    attempt = 0
    while attempt < max_retries:
        try:
            logging.info(f"Attempting to set leverage for {symbol} to {leverage}x on {exchange.id}")
            # Some exchanges might require productType for Bitget e.g. 'USDT-FUTURES' or 'COIN-FUTURES'
            # params = {'productType': 'PERPETUAL'} # Example for some exchanges
            # The exact params might vary or not be needed if defaultType is set on exchange instance
            exchange.set_leverage(leverage, symbol)
            logging.info(f"Successfully set leverage for {symbol} to {leverage}x on {exchange.id}.")
            return True
        except ccxt.NetworkError as e:
            logging.warning(f"Network error setting leverage for {symbol} (attempt {attempt + 1}/{max_retries}): {e}")
            attempt += 1
            time.sleep(delay_seconds)
        except ccxt.ExchangeError as e:
            logging.error(f"Exchange error setting leverage for {symbol} on {exchange.id}: {e}")
            # Some errors might be non-retryable (e.g., invalid symbol, leverage too high)
            # Check e.g. if e contains "leverage not supported" or similar
            return False # For now, assume exchange errors are not retryable here
        except Exception as e:
            logging.error(f"An unexpected error occurred setting leverage for {symbol} (attempt {attempt + 1}/{max_retries}): {e}")
            attempt += 1
            time.sleep(delay_seconds)
    logging.error(f"Failed to set leverage for {symbol} to {leverage}x after {max_retries} retries.")
    return False

def create_market_buy_order_with_cost(exchange, symbol, cost_usdt, leverage=1):
    """
    Places a market buy order based on desired cost (margin) and leverage.
    Size is calculated as: (cost_usdt * leverage) / current_price.
    This is a common way for futures, but check exchange specifics.
    `create_market_buy_order_with_cost` is a CCXT unified method for this.
    """
    try:
        # Fetch current price to estimate size, though create_market_buy_order_with_cost might do this internally
        # ticker = exchange.fetch_ticker(symbol)
        # current_price = ticker['last']
        # amount_asset = (cost_usdt * leverage) / current_price
        
        # CCXT unified method: create_market_buy_order_with_cost(symbol, cost)
        # The 'cost' here is the quote currency amount you want to spend.
        # If this is for margin trading, `cost_usdt` is the margin.
        # The actual position size will be determined by leverage which should be pre-set.
        
        logging.info(f"Placing market buy for {symbol} with cost {cost_usdt} USDT (leverage {leverage}x)")        
        params = {} # Add exchange-specific params if needed
        # For Bitget and some other exchanges, when creating an order with cost,
        # you might need to specify if it's for futures and the type (e.g. USDT-M)
        # if exchange.id == 'bitget':
        #     params['productType'] = 'UMCBL' # For USDT-M Perpetual Futures

        # The `cost` parameter for `create_market_buy_order_with_cost` is the amount of quote currency to spend.
        # If `cost_usdt` is intended as margin, and leverage is applied by the exchange,
        # then the actual quote currency spent to acquire the position would be `cost_usdt`.
        # The position value would be `cost_usdt * leverage`.
        order = exchange.create_market_buy_order_with_cost(symbol, cost_usdt, params=params)
        
        logging.info(f"Market buy order placed for {symbol}: {order['id']}")
        # Structure of returned order varies, but usually includes id, price, amount, cost, filled, etc.
        # For state management: entry_price, position_size
        filled_price = order.get('average') or order.get('price') # average is better if available
        filled_amount = order.get('filled') or order.get('amount')
        
        if filled_price and filled_amount:
            return {
                'status': 'success',
                'id': order['id'],
                'entry_price': filled_price,
                'size': filled_amount,
                'cost': order.get('cost', cost_usdt) # Actual cost from exchange if available
            }
        else:
            logging.warning(f"Market buy order {order['id']} placed but filled details (price/amount) missing.")
            # May need to fetch order status separately if not immediately available
            return {'status': 'pending_check', 'id': order['id']}
            
    except ccxt.InsufficientFunds as e:
        logging.error(f"Insufficient funds to place market buy for {symbol} with cost {cost_usdt}: {e}")
    except ccxt.ExchangeError as e:
        logging.error(f"Exchange error placing market buy for {symbol}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error placing market buy for {symbol}: {e}")
    return {'status': 'error', 'message': str(e) if 'e' in locals() else 'Unknown error'}


# --- Bitget V1 API Specific (Example as per lhl.txt for closing) ---
# Note: CCXT often provides methods to close positions (e.g., create_market_sell_order with reduceOnly param)
# Using direct API calls should be a fallback or for specific non-standard needs.

BITGET_V1_BASE_URL = "https://api.bitget.com" # Use sandbox URL for testing if available

def generate_bitget_v1_signature(timestamp, method, request_path, body_str, api_secret):
    """
    Generates a signature for Bitget API V1.
    Message to sign: timestamp + method + requestPath + body
    """
    if not isinstance(body_str, str):
        body_str = json.dumps(body_str) if body_str else ''
        
    message = str(timestamp) + method.upper() + request_path + body_str
    mac = hmac.new(bytes(api_secret, encoding='utf-8'), bytes(message, encoding='utf-8'), digestmod=hashlib.sha256)
    return mac.digest().hex() # Or base64 depending on API spec, Bitget usually hex for v1, but check docs
    # Re-check Bitget docs: V1 /api/mix/v1/order/placeOrder says base64-encoded SHA256
    # return base64.b64encode(mac.digest()).decode()

def close_long_position_bitget_v1(api_key, api_secret, passphrase, symbol_bitget, size, margin_coin='USDT'):
    """
    Closes a long position using Bitget's V1 API directly.
    (As described in lhl.txt as a specific method being used)
    Endpoint: /api/mix/v1/order/placeOrder (assuming futures/mix account)

    Args:
        symbol_bitget (str): The Bitget specific symbol (e.g., 'BTCUSDT_UMCBL').
        size (str or float): The size of the position to close (in base currency).
        margin_coin (str): The margin coin (e.g., 'USDT').
    """
    timestamp = str(int(time.time() * 1000))
    method = 'POST'
    request_path = '/api/mix/v1/order/placeOrder' # Check if this is correct for closing
    # The doc mentions "close_long" side. This is specific to Bitget's API params.
    body = {
        "symbol": symbol_bitget,
        "marginCoin": margin_coin,
        "size": str(size), # Ensure size is a string
        "side": "close_long", 
        "orderType": "market",
        # "tradeSide": "close" # Some APIs might use this
    }
    body_str = json.dumps(body)

    # Signature needs to be Base64 encoded for Bitget API v1 (as per general Bitget API docs)
    # The signing string is: timestamp + method + requestPath + requestBody
    message_to_sign = timestamp + method + request_path + body_str
    signature_raw = hmac.new(bytes(api_secret, 'utf-8'), bytes(message_to_sign, 'utf-8'), hashlib.sha256).digest()
    signature = base64.b64encode(signature_raw).decode('utf-8')

    headers = {
        'ACCESS-KEY': api_key,
        'ACCESS-SIGN': signature,
        'ACCESS-TIMESTAMP': timestamp,
        'ACCESS-PASSPHRASE': passphrase,
        'Content-Type': 'application/json',
        'X-LOCALE': 'en-US' # Optional, but good practice
    }

    url = BITGET_V1_BASE_URL + request_path
    try:
        logging.info(f"Attempting to close long position for {symbol_bitget}, size {size} via Bitget V1 API.")
        response = requests.post(url, headers=headers, data=body_str, timeout=10)
        response_data = response.json()
        logging.info(f"Bitget V1 close order response: {response_data}")

        if response.status_code == 200 and response_data.get("code") == "00000": # "00000" is often success for Bitget
            logging.info(f"Successfully submitted close order for {symbol_bitget} via Bitget V1 API. Order ID: {response_data.get('data',{}).get('orderId')}")
            return {'status': 'success', 'data': response_data.get('data')}
        else:
            logging.error(f"Error closing position via Bitget V1 API: {response_data}")
            return {'status': 'error', 'message': response_data.get('msg', 'Unknown Bitget API error'), 'data': response_data}

    except requests.exceptions.RequestException as e:
        logging.error(f"Network error during Bitget V1 API call: {e}")
        return {'status': 'error', 'message': f"Network error: {e}"}
    except Exception as e:
        logging.error(f"Unexpected error during Bitget V1 API call: {e}")
        return {'status': 'error', 'message': f"Unexpected error: {e}"}

# --- General Utilities ---

def format_bitget_symbol_for_ccxt(bitget_symbol):
    """
    Converts a Bitget trading pair symbol (e.g., BTCUSDT_UMCBL for USDT-M futures)
    to a format CCXT might prefer or understand if it doesn't map it automatically.
    CCXT usually prefers "BTC/USDT" for spot and might need type specification for futures.
    For Bitget with CCXT, it often handles symbols like 'BTC/USDT:USDT' for USDT-margined SWAP.
    Or, the exchange object's `options['defaultType'] = 'swap'` can simplify this.
    """
    # This is a placeholder. Actual conversion depends on how CCXT handles Bitget symbols
    # and whether you are trading spot, USDT-M futures, COIN-M futures etc.
    if bitget_symbol.endswith("_UMCBL"): # USDT-M Perpetual Futures (unified account)
        base = bitget_symbol.replace("_UMCBL", "")
        if base.endswith("USDT"):
            return base[:-4] + "/" + "USDT:USDT" # e.g., BTC/USDT:USDT
        # Add other quote currencies if needed
    elif bitget_symbol.endswith("_CMCBL"): # COIN-M Perpetual Futures
        # e.g. BTCUSD_CMCBL -> BTC/USD:BTC
        pass 
    elif "/" not in bitget_symbol and bitget_symbol.isupper(): # Potentially a spot symbol like BTCUSDT
        if bitget_symbol.endswith("USDT"):
            return bitget_symbol[:-4] + "/USDT"
        # Add other common quote currencies
    
    logging.warning(f"Unsure how to convert Bitget symbol '{bitget_symbol}' to CCXT format. Returning as is.")
    return bitget_symbol

def format_ccxt_symbol_for_bitget_api(ccxt_symbol, product_type='UMCBL'):
    """
    Converts a CCXT symbol (e.g., 'BTC/USDT', or 'BTC/USDT:USDT') to a Bitget API specific symbol 
    (e.g., 'BTCUSDT_UMCBL') if direct API calls are made.
    """
    parts = ccxt_symbol.replace(":USDT","").split('/')
    if len(parts) == 2:
        base, quote = parts[0], parts[1]
        if quote == 'USDT' and product_type == 'UMCBL':
            return f"{base}{quote}_{product_type}" # BTCUSDT_UMCBL
        # Add other product types and quote logic as needed
    
    logging.warning(f"Could not convert CCXT symbol '{ccxt_symbol}' to Bitget API format for type '{product_type}'. Using base part.")
    return ccxt_symbol.split('/')[0] + "USDT_" + product_type # Fallback guess


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    print("--- Testing Utility Functions ---")

    # Test Bitget symbol conversion
    print("\n--- Symbol Conversion Tests ---")
    ccxt_sym = 'BTC/USDT:USDT'
    api_sym = format_ccxt_symbol_for_bitget_api(ccxt_sym, product_type='UMCBL')
    print(f"CCXT '{ccxt_sym}' to Bitget API (UMCBL): '{api_sym}'")
    assert api_sym == "BTCUSDT_UMCBL"

    api_sym_direct = 'ETHUSDT_UMCBL'
    ccxt_sym_converted = format_bitget_symbol_for_ccxt(api_sym_direct)
    print(f"Bitget API '{api_sym_direct}' to CCXT: '{ccxt_sym_converted}'")
    assert ccxt_sym_converted == "ETH/USDT:USDT"

    spot_api_sym = 'LTCUSDT'
    spot_ccxt_sym = format_bitget_symbol_for_ccxt(spot_api_sym)
    print(f"Bitget API Spot '{spot_api_sym}' to CCXT: '{spot_ccxt_sym}'")
    assert spot_ccxt_sym == "LTC/USDT"

    # --- Test Bitget V1 API Signature (Example - DO NOT USE REAL KEYS HERE) ---
    # This requires actual (dummy) keys to fully test, but we can test the signing function structure.
    print("\n--- Bitget V1 Signature Generation (Structure Test) ---")
    dummy_api_key = "bg_xxxxxxxx"
    dummy_api_secret = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    dummy_passphrase = "xxxxxxxxx"
    ts = str(int(time.time() * 1000))
    meth = 'POST'
    path = '/api/mix/v1/order/placeOrder'
    body_example = {"symbol": "BTCUSDT_UMCBL", "marginCoin": "USDT", "size": "0.001", "side": "open_long", "orderType": "market"}
    body_s = json.dumps(body_example)
    
    # Corrected Bitget V1 signing (timestamp + method + requestPath + requestBody)
    # And Base64 encoding of the HMAC-SHA256 digest
    message_to_sign_test = ts + meth + path + body_s
    signature_raw_test = hmac.new(bytes(dummy_api_secret, 'utf-8'), bytes(message_to_sign_test, 'utf-8'), hashlib.sha256).digest()
    signature_test = base64.b64encode(signature_raw_test).decode('utf-8')
    print(f"Timestamp: {ts}")
    print(f"Message signed: {message_to_sign_test[:100]}...") # Print only part of it
    print(f"Generated Signature (example): {signature_test}")
    # The close_long_position_bitget_v1 function implements this.

    print("\nNote: Full API call tests (set_leverage, order placement, close) are better done with mocks or against a sandbox.")
    print("The `trading_bot.py` and `data_fetcher.py` will use these utilities.")

    # To test actual Bitget V1 close, you would need to:
    # 1. Have a position to close on Bitget (sandbox/testnet ideally).
    # 2. Fill in YOUR_API_KEY, YOUR_API_SECRET, YOUR_PASSPHRASE below.
    # 3. Specify the correct Bitget symbol and size.
    # -----
    # API_KEY_REAL = "YOUR_API_KEY" 
    # API_SECRET_REAL = "YOUR_API_SECRET"
    # API_PASSPHRASE_REAL = "YOUR_PASSPHRASE"
    # BITGET_SYMBOL_TO_CLOSE = "SBTCSUSDT_SUMCBL" # Example Sandbox symbol
    # POSITION_SIZE_TO_CLOSE = "0.01"
    # if API_KEY_REAL != "YOUR_API_KEY":
    #     print("\n--- Attempting Real Bitget V1 Close (ensure sandbox and dummy funds) ---")
    #     close_result = close_long_position_bitget_v1(
    #         API_KEY_REAL, API_SECRET_REAL, API_PASSPHRASE_REAL, 
    #         BITGET_SYMBOL_TO_CLOSE, POSITION_SIZE_TO_CLOSE
    #     )
    #     print(f"Close Result: {close_result}")
    # else:
    #     print("\nSkipping real Bitget V1 close test (API keys not set).")
    # -----

    # Note on CCXT close: Often, you can close a position by placing an opposite order.
    # For example, if long 0.1 BTC/USDT, place a market sell of 0.1 BTC/USDT.
    # Many exchanges support a `reduceOnly` parameter for this to ensure it only closes
    # and doesn't open a new position if sizes mismatch or position doesn't exist.
    # e.g., exchange.create_order(symbol, 'market', 'sell', amount, params={'reduceOnly': True}) 