import pandas as pd
import ast

def processing(dfs):
    """
    Counts how many orders used a coupon by parsing the 'details' column.
    """
    orders_df = dfs[0]

    def has_coupon(row_str):
        try:
            # Parse the string representation of a dictionary
            data_dict = ast.literal_eval(row_str)
            # An order used a coupon if 'coupon' key is present AND its value is not None
            if 'coupon' in data_dict and data_dict['coupon'] is not None:
                return True
            return False
        except (ValueError, SyntaxError):
            # In case of malformed data
            return False

    # Apply the logic and sum the True values
    orders_df['used_coupon'] = orders_df['details'].apply(has_coupon)
    
    # Count the total number of orders that used a coupon
    coupon_order_count = orders_df['used_coupon'].sum()
    
    # Return the result as a DataFrame
    return pd.DataFrame({'coupon_order_count': [coupon_order_count]})