from typing import List, Any, Optional
from statistics import mean
from collections import Counter


def calculate_average_temperature(temperatures: List[float]) -> Optional[float]:
    """Calculate the average temperature."""
    return mean(temperatures) if temperatures else None


def get_max_temperature(temperatures: List[float]) -> Optional[float]:
    """Get the maximum temperature."""
    return max(temperatures) if temperatures else None


def get_most_common_value(values: List[Any]) -> Optional[Any]:
    """Get the most common value from a list."""
    return Counter(values).most_common(1)[0][0] if values else None
