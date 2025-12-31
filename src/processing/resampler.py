"""
Time-Series Resampling Module
============================
Aligns multi-rate sensor channels to a common timebase.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from scipy import interpolate


class Resampler:
    """
    Resamples time-series data from various sample rates to a common rate.
    Supports multiple interpolation methods for different sensor types.
    """
    
    def __init__(self, target_hz: float = 100.0):
        """
        Initialize resampler.
        
        Args:
            target_hz: Target sample rate in Hz
        """
        self.target_hz = target_hz
        self.dt = 1.0 / target_hz
    
    def resample_channel(
        self,
        timestamps: np.ndarray,
        values: np.ndarray,
        method: str = 'linear'
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Resample a single channel to the target rate.
        
        Args:
            timestamps: Array of timestamps (as floats, seconds from start)
            values: Array of sensor values
            method: Interpolation method ('linear', 'cubic', 'nearest')
            
        Returns:
            Tuple of (new_timestamps, resampled_values)
        """
        if len(timestamps) < 2:
            return timestamps, values
        
        # Create target time array
        t_start = timestamps[0]
        t_end = timestamps[-1]
        n_samples = int((t_end - t_start) * self.target_hz) + 1
        t_new = np.linspace(t_start, t_end, n_samples)
        
        # Interpolate
        if method == 'linear':
            interp_func = interpolate.interp1d(
                timestamps, values, 
                kind='linear', 
                fill_value='extrapolate',
                bounds_error=False
            )
        elif method == 'cubic':
            # Use cubic spline for smooth signals
            interp_func = interpolate.interp1d(
                timestamps, values,
                kind='cubic',
                fill_value='extrapolate',
                bounds_error=False
            )
        elif method == 'nearest':
            # Use nearest for discrete/digital signals
            interp_func = interpolate.interp1d(
                timestamps, values,
                kind='nearest',
                fill_value='extrapolate',
                bounds_error=False
            )
        else:
            raise ValueError(f"Unknown interpolation method: {method}")
        
        v_new = interp_func(t_new)
        
        return t_new, v_new
    
    def resample_run(
        self,
        samples: List[Dict],
        channel_methods: Optional[Dict[int, str]] = None
    ) -> Dict[int, Tuple[np.ndarray, np.ndarray]]:
        """
        Resample all channels in a run to a common timebase.
        
        Args:
            samples: List of sample dicts with channel_id, ts, value
            channel_methods: Optional dict mapping channel_id to interpolation method
                             Defaults to 'linear' for all channels
        
        Returns:
            Dict mapping channel_id to (timestamps, values) tuples
        """
        if channel_methods is None:
            channel_methods = {}
        
        # Group samples by channel
        channel_data: Dict[int, Tuple[List[float], List[float]]] = {}
        
        # Find the base timestamp for relative time calculation
        base_ts = None
        for sample in samples:
            ts = sample['ts']
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            if base_ts is None or ts < base_ts:
                base_ts = ts
        
        # Group and convert to relative timestamps
        for sample in samples:
            channel_id = sample['channel_id']
            ts = sample['ts']
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            
            # Convert to seconds from start
            if hasattr(ts, 'timestamp'):
                rel_time = (ts - base_ts).total_seconds()
            else:
                rel_time = float(ts)
            
            value = float(sample['value'])
            
            if channel_id not in channel_data:
                channel_data[channel_id] = ([], [])
            
            channel_data[channel_id][0].append(rel_time)
            channel_data[channel_id][1].append(value)
        
        # Resample each channel
        resampled: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}
        
        for channel_id, (times, values) in channel_data.items():
            # Sort by time
            sorted_indices = np.argsort(times)
            t_arr = np.array(times)[sorted_indices]
            v_arr = np.array(values)[sorted_indices]
            
            # Get interpolation method for this channel
            method = channel_methods.get(channel_id, 'linear')
            
            # Resample
            t_new, v_new = self.resample_channel(t_arr, v_arr, method)
            resampled[channel_id] = (t_new, v_new)
        
        return resampled
    
    def align_channels(
        self,
        resampled_data: Dict[int, Tuple[np.ndarray, np.ndarray]]
    ) -> Tuple[np.ndarray, Dict[int, np.ndarray]]:
        """
        Align all resampled channels to a common time array.
        
        Args:
            resampled_data: Dict from resample_run
            
        Returns:
            Tuple of (common_timestamps, {channel_id: values})
        """
        if not resampled_data:
            return np.array([]), {}
        
        # Find common time range
        t_start = max(data[0][0] for data in resampled_data.values())
        t_end = min(data[0][-1] for data in resampled_data.values())
        
        # Create common time array
        n_samples = int((t_end - t_start) * self.target_hz) + 1
        common_time = np.linspace(t_start, t_end, n_samples)
        
        # Interpolate each channel to common time
        aligned: Dict[int, np.ndarray] = {}
        
        for channel_id, (times, values) in resampled_data.items():
            interp_func = interpolate.interp1d(
                times, values,
                kind='linear',
                fill_value='extrapolate',
                bounds_error=False
            )
            aligned[channel_id] = interp_func(common_time)
        
        return common_time, aligned


def resample_samples(
    samples: List[Dict],
    target_hz: float = 100.0
) -> Dict[int, Tuple[np.ndarray, np.ndarray]]:
    """
    Convenience function to resample sample data.
    
    Args:
        samples: List of sample dicts
        target_hz: Target sample rate
        
    Returns:
        Dict mapping channel_id to (timestamps, values) tuples
    """
    resampler = Resampler(target_hz=target_hz)
    return resampler.resample_run(samples)


if __name__ == "__main__":
    # Test the resampler
    print("🔄 Testing Resampler")
    print("=" * 50)
    
    # Create test data at 1000 Hz
    n_samples = 1000
    t = np.linspace(0, 1, n_samples)  # 1 second at 1000 Hz
    v = np.sin(2 * np.pi * 5 * t) + np.random.normal(0, 0.1, n_samples)
    
    samples = [
        {'channel_id': 1, 'ts': ti, 'value': vi}
        for ti, vi in zip(t, v)
    ]
    
    # Resample to 100 Hz
    resampler = Resampler(target_hz=100)
    resampled = resampler.resample_run(samples)
    
    t_new, v_new = resampled[1]
    print(f"Original: {len(t)} samples at 1000 Hz")
    print(f"Resampled: {len(t_new)} samples at 100 Hz")
    print(f"Time range: {t_new[0]:.3f}s to {t_new[-1]:.3f}s")
    
    print("\n✅ Resampler working!")
