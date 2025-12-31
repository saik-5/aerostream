"""
De-spiking Module (MAD Algorithm)
=================================
Removes sensor glitches using Median Absolute Deviation (MAD).
"""

import numpy as np
from typing import Tuple, Optional, Dict, List
from dataclasses import dataclass


@dataclass
class DespikeResult:
    """Results from de-spiking operation."""
    original: np.ndarray
    cleaned: np.ndarray
    spike_mask: np.ndarray
    spike_count: int
    spike_pct: float
    spike_indices: np.ndarray


class Despiker:
    """
    Removes spikes from time-series data using MAD algorithm.
    
    MAD = median(|x - median(x)|)
    threshold = median ± k * MAD * 1.4826
    
    The 1.4826 factor makes MAD consistent with standard deviation
    for normally distributed data.
    """
    
    # Scale factor to make MAD consistent with std for normal distributions
    MAD_SCALE = 1.4826
    
    def __init__(
        self,
        threshold: float = 3.5,
        window_size: Optional[int] = None,
        replace_method: str = 'interpolate'
    ):
        """
        Initialize the despiker.
        
        Args:
            threshold: Number of MAD units for spike detection (3.5 is common)
            window_size: Rolling window size for local MAD calculation
                        None = use global MAD
            replace_method: How to replace spikes:
                           'interpolate' - linear interpolation
                           'median' - replace with median
                           'nan' - replace with NaN
        """
        self.threshold = threshold
        self.window_size = window_size
        self.replace_method = replace_method
    
    def calculate_mad(self, data: np.ndarray) -> Tuple[float, float]:
        """
        Calculate the Median Absolute Deviation.
        
        Args:
            data: Input array
            
        Returns:
            Tuple of (median, MAD)
        """
        median = np.median(data)
        mad = np.median(np.abs(data - median))
        return median, mad
    
    def detect_spikes(
        self,
        values: np.ndarray
    ) -> np.ndarray:
        """
        Detect spikes in the data.
        
        Args:
            values: Array of sensor values
            
        Returns:
            Boolean mask where True indicates a spike
        """
        if self.window_size is None:
            # Global MAD calculation
            median, mad = self.calculate_mad(values)
            if mad == 0:
                # No variation, no spikes
                return np.zeros(len(values), dtype=bool)
            
            lower = median - self.threshold * mad * self.MAD_SCALE
            upper = median + self.threshold * mad * self.MAD_SCALE
            spike_mask = (values < lower) | (values > upper)
        else:
            # Rolling window MAD calculation
            spike_mask = np.zeros(len(values), dtype=bool)
            half_window = self.window_size // 2
            
            for i in range(len(values)):
                start = max(0, i - half_window)
                end = min(len(values), i + half_window + 1)
                window = values[start:end]
                
                median, mad = self.calculate_mad(window)
                if mad == 0:
                    continue
                
                lower = median - self.threshold * mad * self.MAD_SCALE
                upper = median + self.threshold * mad * self.MAD_SCALE
                
                if values[i] < lower or values[i] > upper:
                    spike_mask[i] = True
        
        return spike_mask
    
    def replace_spikes(
        self,
        timestamps: np.ndarray,
        values: np.ndarray,
        spike_mask: np.ndarray
    ) -> np.ndarray:
        """
        Replace detected spikes with interpolated/median values.
        
        Args:
            timestamps: Time array
            values: Value array
            spike_mask: Boolean mask of spikes
            
        Returns:
            Cleaned values array
        """
        cleaned = values.copy()
        
        if not np.any(spike_mask):
            return cleaned
        
        if self.replace_method == 'nan':
            cleaned[spike_mask] = np.nan
            
        elif self.replace_method == 'median':
            median = np.median(values[~spike_mask])
            cleaned[spike_mask] = median
            
        elif self.replace_method == 'interpolate':
            # Get indices of good and bad points
            good_indices = np.where(~spike_mask)[0]
            bad_indices = np.where(spike_mask)[0]
            
            if len(good_indices) < 2:
                # Not enough good points, use median
                cleaned[spike_mask] = np.median(values)
            else:
                # Interpolate bad points from good points
                cleaned[bad_indices] = np.interp(
                    timestamps[bad_indices],
                    timestamps[good_indices],
                    values[good_indices]
                )
        else:
            raise ValueError(f"Unknown replace method: {self.replace_method}")
        
        return cleaned
    
    def despike(
        self,
        timestamps: np.ndarray,
        values: np.ndarray
    ) -> DespikeResult:
        """
        Detect and remove spikes from the data.
        
        Args:
            timestamps: Time array
            values: Value array
            
        Returns:
            DespikeResult with cleaned data and spike statistics
        """
        spike_mask = self.detect_spikes(values)
        cleaned = self.replace_spikes(timestamps, values, spike_mask)
        
        spike_indices = np.where(spike_mask)[0]
        spike_count = len(spike_indices)
        spike_pct = 100.0 * spike_count / len(values) if len(values) > 0 else 0.0
        
        return DespikeResult(
            original=values,
            cleaned=cleaned,
            spike_mask=spike_mask,
            spike_count=spike_count,
            spike_pct=spike_pct,
            spike_indices=spike_indices
        )


def despike_channel(
    timestamps: np.ndarray,
    values: np.ndarray,
    threshold: float = 3.5,
    window_size: Optional[int] = None
) -> Tuple[np.ndarray, int, float]:
    """
    Convenience function to despike a channel.
    
    Args:
        timestamps: Time array
        values: Value array
        threshold: MAD threshold
        window_size: Optional rolling window size
        
    Returns:
        Tuple of (cleaned_values, spike_count, spike_pct)
    """
    despiker = Despiker(threshold=threshold, window_size=window_size)
    result = despiker.despike(timestamps, values)
    return result.cleaned, result.spike_count, result.spike_pct


def despike_run(
    channel_data: Dict[int, Tuple[np.ndarray, np.ndarray]],
    threshold: float = 3.5
) -> Dict[int, DespikeResult]:
    """
    Despike all channels in a run.
    
    Args:
        channel_data: Dict mapping channel_id to (timestamps, values)
        threshold: MAD threshold for spike detection
        
    Returns:
        Dict mapping channel_id to DespikeResult
    """
    despiker = Despiker(threshold=threshold)
    results = {}
    
    for channel_id, (timestamps, values) in channel_data.items():
        results[channel_id] = despiker.despike(timestamps, values)
    
    return results


if __name__ == "__main__":
    # Test the despiker
    print("🔧 Testing Despiker (MAD Algorithm)")
    print("=" * 50)
    
    # Create test data with spikes
    np.random.seed(42)
    n_samples = 1000
    t = np.linspace(0, 10, n_samples)
    
    # Base signal: sine wave with noise
    v = np.sin(2 * np.pi * 0.5 * t) + np.random.normal(0, 0.1, n_samples)
    
    # Add some spikes
    spike_indices = [100, 250, 500, 750, 900]
    for idx in spike_indices:
        v[idx] = v[idx] + np.random.choice([-1, 1]) * 5  # Large spike
    
    print(f"Created {n_samples} samples with {len(spike_indices)} artificial spikes")
    
    # Despike
    despiker = Despiker(threshold=3.5)
    result = despiker.despike(t, v)
    
    print(f"\nResults:")
    print(f"  Spikes detected: {result.spike_count}")
    print(f"  Spike percentage: {result.spike_pct:.2f}%")
    print(f"  Detected indices: {result.spike_indices.tolist()}")
    print(f"  Expected indices: {spike_indices}")
    
    # Check if we found all the spikes
    detected = set(result.spike_indices.tolist())
    expected = set(spike_indices)
    if expected.issubset(detected):
        print("\n✅ All artificial spikes detected!")
    else:
        missed = expected - detected
        print(f"\n⚠️ Missed spikes at indices: {missed}")
    
    print("\n✅ Despiker working!")
