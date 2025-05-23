import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from support_resistance import find_lhl_support_resistance
from live_signal_bot import get_closest_sr_levels

def generate_test_data():
    """Generate test data with known support levels"""
    end_date = datetime.now()
    dates = [end_date - timedelta(minutes=i) for i in range(500)]
    dates.reverse()
    
    # Create price data with known support levels
    base_price = 100
    prices = []
    current_price = base_price
    
    # Create a strong support level around 98
    # This will be done by creating multiple LHL patterns at this level
    for i in range(500):
        if i < 400:  # Historical data
            # Create oscillating patterns with support at 95
            if i % 30 == 0:
                current_price = 95 + np.random.normal(0, 0.1)
            elif i % 15 == 0:
                current_price = 97 + np.random.normal(0, 0.5)
            else:
                current_price += np.random.normal(0, 0.2)
        else:  # Recent data - create strong support at 98
            if len(prices) >= 2:
                # Create LHL patterns with support at 98
                if i % 20 == 0:
                    current_price = 98 + np.random.normal(0, 0.1)  # Support level
                elif i % 10 == 0:
                    current_price = 99 + np.random.normal(0, 0.2)  # Higher high
                else:
                    # Gradually approach the 98 level
                    target = 98 if current_price > 98 else 99
                    current_price += (target - current_price) * 0.1 + np.random.normal(0, 0.1)
            
        # Keep price positive and somewhat stable
        current_price = max(90, min(105, current_price))
        prices.append(current_price)
    
    # Create test DataFrame
    df = pd.DataFrame({
        'timestamp': dates,
        'Close': prices
    })
    
    return df

def test_support_detection():
    """Test the support level detection logic"""
    print("Starting support detection test...")
    
    # Generate test data
    test_data = generate_test_data()
    current_price = test_data['Close'].iloc[-1]
    
    print(f"\nTest 1: Basic Support Level Detection")
    print("-" * 50)
    
    # Test with normal configuration
    config = {
        'sr_price_tolerance': 0.01,
        'entry_proximity': 0.005
    }
    
    sr_levels = get_closest_sr_levels(current_price, test_data, config)
    
    if not sr_levels.empty:
        print("\nDetected Support Levels:")
        supports = sr_levels[sr_levels['Type'] == 'Support']
        for _, row in supports.iterrows():
            print(f"{row['Tier']}: {row['Price']:.2f}")
              # Verify we have both recent and historical supports
        s1_price = supports[supports['Tier'] == 'S1']['Price'].iloc[0]
        print(f"\nS1 Level: {s1_price:.2f}")
        assert abs(s1_price - 98) < 1.5, "S1 should be around 98 (±1.5)"
        
        if len(supports) > 1:
            s2_price = supports[supports['Tier'] == 'S2']['Price'].iloc[0]
            print(f"S2 Level: {s2_price:.2f}")
            assert abs(s2_price - 95) < 1.5, "S2 should be around 95 (±1.5)"
            
        print("\nTest passed: Support levels detected correctly")
    else:
        print("Error: No support levels detected")
        return False
    
    print("\nTest 2: Support Level Transitions")
    print("-" * 50)
    
    # Create a new price point near 98 to test support level transition
    test_data.loc[len(test_data)] = [
        datetime.now(),
        97.9  # Price near the recent support
    ]
    current_price = 97.9
    
    sr_levels = get_closest_sr_levels(current_price, test_data, config)
    
    if not sr_levels.empty:
        supports = sr_levels[sr_levels['Type'] == 'Support']
        s1_price = supports[supports['Tier'] == 'S1']['Price'].iloc[0]
        print(f"\nUpdated S1 Level: {s1_price:.2f}")
        assert abs(s1_price - 98) < 1.5, "S1 should still be around 98 (±1.5) as price approaches it"
        print("Test passed: Support level transition works correctly")
    else:
        print("Error: No support levels detected after transition")
        return False
    
    print("\nAll tests passed successfully!")
    return True

if __name__ == "__main__":
    test_support_detection()
