import pandas as pd
import ast

def processing(dfs):
    """
    Parses the JSON-like 'details' column to extract the city and counts orders
    shipped to 'Lyon' with status 'delivered'.
    """
    # Load the orders DataFrame
    df = dfs[0]

    # Filter by the 'delivered' status first
    df_filtered = df[df['status'] == 'delivered'].copy()

    # Helper function to parse dictionary string and extract the city
    def get_city(details):
        try:
            # Use ast.literal_eval for safely evaluating Python-formatted dictionary strings
            if isinstance(details, str):
                details_dict = ast.literal_eval(details)
            else:
                details_dict = details
            
            # Navigate the structure to get the city
            # Path: shipping -> address -> city
            if isinstance(details_dict, dict):
                shipping = details_dict.get('shipping')
                if isinstance(shipping, dict):
                    address = shipping.get('address')
                    if isinstance(address, dict):
                        return address.get('city')
        except (ValueError, SyntaxError, AttributeError, TypeError):
            # Return None if parsing fails or structure is unexpected
            return None
        return None

    # Apply the helper function to extract the city
    df_filtered['city'] = df_filtered['details'].apply(get_city)

    # Filter for orders shipped to 'Lyon'
    df_result = df_filtered[df_filtered['city'] == 'Lyon']

    # Get the count
    count = len(df_result)

    # Return the result as a DataFrame
    return pd.DataFrame({'count': [count]})