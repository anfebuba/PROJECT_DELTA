import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from support_resistance import find_lhl_support_resistance

def generate_sample_data(minutes=300):
    """Generate sample price data with clear LHL patterns"""
    timestamps = [datetime.now() + timedelta(minutes=i*5) for i in range(minutes)]
    
    # Generate a price series with clear LHL patterns
    prices = []
    base_price = 100
    for i in range(minutes):
        if i < minutes/3:  # First third: forming first LHL
            price = base_price + np.sin(i/10) * 2
        elif i < minutes*2/3:  # Second third: forming second LHL at higher level
            price = base_price + 5 + np.sin(i/10) * 2
        else:  # Last third: forming third LHL at lower level
            price = base_price - 2 + np.sin(i/10) * 2
        prices.append(price)
    
    df = pd.DataFrame({
        'timestamp': timestamps,
        'Close': prices
    })
    return df

def plot_sr_updates(price_data, window_size=50):
    """Plot price data with dynamically updating S/R levels"""
    fig, ax = plt.subplots(figsize=(15, 8))
    
    # Plot full price data
    ax.plot(range(len(price_data)), price_data['Close'], label='Price', color='blue', alpha=0.5)
    
    # Calculate and plot S/R levels for each window
    for i in range(window_size, len(price_data), window_size//2):
        window_data = price_data.iloc[max(0, i-200):i]  # Use last 200 candles
        sr_df = find_lhl_support_resistance(
            window_data,
            tolerance_percent=0.005,
            window_size=10,
            sr_count=10
        )
        
        if not sr_df.empty:
            # Plot S1 and R1 levels
            s1 = sr_df[sr_df['Tier'] == 'S1'].iloc[0]['Price'] if not sr_df[sr_df['Tier'] == 'S1'].empty else None
            r1 = sr_df[sr_df['Tier'] == 'R1'].iloc[0]['Price'] if not sr_df[sr_df['Tier'] == 'R1'].empty else None
            
            if s1:
                ax.hlines(y=s1, xmin=i-window_size, xmax=i, color='green', linestyles='--', alpha=0.5)
            if r1:
                ax.hlines(y=r1, xmin=i-window_size, xmax=i, color='red', linestyles='--', alpha=0.5)
    
    plt.title('Price Data with Dynamically Updating S/R Levels')
    plt.xlabel('Candle Number')
    plt.ylabel('Price')
    plt.grid(True)
    plt.legend()
    plt.show()

def main():
    # Generate sample data
    print("Generating sample data...")
    df = generate_sample_data()
    
    # Plot with dynamic S/R updates
    print("Plotting price data with dynamic S/R updates...")
    plot_sr_updates(df)

if __name__ == "__main__":
    main()
