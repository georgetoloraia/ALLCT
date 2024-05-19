import numpy as np
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def avl(prices, volumes):
    """
    Calculate the Average Value Line (AVL), which is a volume-weighted average of prices.

    Parameters:
    prices (pd.Series): Series containing price data.
    volumes (pd.Series): Series containing volume data corresponding to the prices.

    Returns:
    float: The calculated AVL value or None if volumes sum to zero.
    """
    # Check if prices and volumes are pandas Series
    if not isinstance(prices, pd.Series) or not isinstance(volumes, pd.Series):
        logger.error("Input prices and volumes must be pandas Series.")
        return None

    try:
        if volumes.sum() == 0:
            logger.warning("Total volume is zero, cannot compute AVL.")
            return None
        vwap = (prices * volumes).sum() / volumes.sum()
        return vwap
    except Exception as e:
        logger.error(f"Error computing AVL: {str(e)}")
        return None






'''
def avl(prices, volumes):
    if volumes.sum() == 0:
        return None  # Avoid division by zero
    return (prices * volumes).sum() / volumes.sum()
'''