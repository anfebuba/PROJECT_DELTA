import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from support_resistance import find_lhl_support_resistance

def generate_test_data(num_points=1000):
    """Generate synthetic price data with some clear LHL patterns"""
    # Create timestamps
    base_time = datetime.now() - timedelta(days=num_points)
    timestamps = [base_time + timedelta(hours=i) for i in range(num_points)]
    
    # Generate base price with some clear LHL patterns
    np.random.seed(42)  # For reproducibility
    base_price = 100
    prices = []
    current_price = base_price
    
    # Create some artificial LHL patterns
    for i in range(num_points):
        # Add some random walk
        change = np.random.normal(0, 0.5)
        current_price += change
        
        # Create some clear LHL patterns at specific intervals
        if i % 100 == 0:  # Every 100 points, create an LHL pattern
            # First low
            current_price -= 2
            prices.append(current_price)
            # High
            current_price += 4
            prices.append(current_price)
            # Second low (similar to first low)
            current_price -= 2.1
            prices.append(current_price)
        else:
            prices.append(current_price)
    
    # Create DataFrame
    df = pd.DataFrame({
        'timestamp': timestamps,
        'Close': prices
    })
    return df

def plot_sr_levels(df, sr_df):
    """Plot price data with support and resistance levels"""
    plt.figure(figsize=(15, 8))
    
    # Plot price data
    plt.plot(df['timestamp'], df['Close'], label='Price', color='blue', alpha=0.5)
    
    # Plot support levels
    support_levels = sr_df[sr_df['Type'] == 'Support']
    for _, level in support_levels.iterrows():
        plt.axhline(y=level['Price'], color='g', linestyle='--', alpha=0.5,
                   label=f"{level['Tier']} ({level['Price']:.2f})")
    
    # Plot resistance levels
    resistance_levels = sr_df[sr_df['Type'] == 'Resistance']
    for _, level in resistance_levels.iterrows():
        plt.axhline(y=level['Price'], color='r', linestyle='--', alpha=0.5,
                   label=f"{level['Tier']} ({level['Price']:.2f})")
    
    plt.title('Price Data with Support and Resistance Levels')
    plt.xlabel('Time')
    plt.ylabel('Price')
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def main():
    # Generate test data
    print("Generating test data...")
    df = generate_test_data()
    
    # Find support and resistance levels
    print("\nFinding support and resistance levels...")
    sr_df = find_lhl_support_resistance(
        df,
        tolerance_percent=0.005,  # 0.5% tolerance
        window_size=10,          # Look at 10 points on each side for extrema
        sr_count=5              # Get top 5 levels of each type
    )
    
    # Print the results
    print("\nSupport and Resistance Levels:")
    print(sr_df)
    
    # Plot the results
    print("\nGenerating plot...")
    plot_sr_levels(df, sr_df)

if __name__ == "__main__":
    main() 