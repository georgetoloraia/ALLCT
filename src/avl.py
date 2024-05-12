def avl(prices, volumes):
    if volumes.sum() == 0:
        return None  # Avoid division by zero
    return (prices * volumes).sum() / volumes.sum()
