#import numpy as np

MIN_SIZE=0
"""This is the minimum size allowed!"""
MAX_SIZE=1000
"""
This is the maximum size allowed!<br/>
(This number may vary based on <b>run context</b>...)
docs : conditional_value
docs : virtual_value=500 to 1000 
"""
MIN_SIZE=-1
"""This is considered a duplicate docstring, and is therefore ignored!"""

_pro_min_size=-2
__pri_min_size=-3

def mini(x, y):
    """
    Take the max between two numbers

    **Parameters**

    > **x:** `float` -- Description of parameter `x`.

    > **y:** `float` -- Description of parameter `y`.

    **Returns**

    > `float` -- Description of returned object.
    """
    #return np.min(x, y)
    return y


def mini2peutetre(x, y):
    """
    Take the max between two numbers

    **Parameters**

    > **x:** `float` -- Description of parameter `x`.

    > **y:** `float` -- Description of parameter `y`.

    **Returns**

    > `float` -- Description of returned object.
    """
    #return np.min(x, y)
    return y
