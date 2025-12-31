"""
Wind Tunnel Sensor Simulator
=============================
Physics-based synthetic data generation for motorsport wind tunnel testing.
Generates 72 channels with variable sample rates and realistic correlations.
"""

import numpy as np
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Generator, Optional
import json


@dataclass
class RunConfiguration:
    """Configuration for a wind tunnel test run."""
    
    # Run identification
    name: str = "Test Run"
    
    # Tunnel conditions
    tunnel_speed: float = 50.0       # m/s (40-60 typical for F1)
    tunnel_aoa: float = 0.0          # degrees, angle of attack (-5 to +5)
    tunnel_yaw: float = 0.0          # degrees, yaw angle (-10 to +10)
    tunnel_temp: float = 20.0        # °C
    tunnel_humidity: float = 45.0    # %
    tunnel_baro: float = 101325.0    # Pa, barometric pressure
    
    # Model configuration
    ride_height_f: float = 30.0      # mm, front ride height (25-40)
    ride_height_r: float = 50.0      # mm, rear ride height (40-70)
    
    # Aerodynamic variant
    variant: str = "baseline"        # baseline, variant_a, variant_b
    
    # Run parameters
    duration_seconds: float = 10.0
    notes: str = ""


# Aerodynamic variants for A/B testing
AERO_VARIANTS = {
    "baseline": {
        "Cl": 3.5,           # Lift coefficient (produces downforce)
        "Cd": 0.90,          # Drag coefficient
        "Cy_per_deg": 0.02,  # Side force per degree yaw
        "aero_balance": 0.45, # Front aero balance (45% front)
        "fw_fraction": 0.33,  # Front wing fraction of total downforce
        "rw_fraction": 0.37,  # Rear wing fraction
    },
    "variant_a": {
        "Cl": 3.7,           # +5.7% downforce
        "Cd": 0.92,          # +2.2% drag
        "Cy_per_deg": 0.022,
        "aero_balance": 0.44,
        "fw_fraction": 0.35,
        "rw_fraction": 0.38,
    },
    "variant_b": {
        "Cl": 3.4,           # -2.9% downforce
        "Cd": 0.85,          # -5.6% drag (low-drag config)
        "Cy_per_deg": 0.018,
        "aero_balance": 0.46,
        "fw_fraction": 0.31,
        "rw_fraction": 0.36,
    },
}


# Pressure coefficient (Cp) distributions by location
CP_DISTRIBUTIONS = {
    # Front wing pressure taps
    "fw_le": (-2.8, 0.2),    # Leading edge: high suction
    "fw_mid": (-3.2, 0.25),  # Mid-chord: peak suction
    "fw_te": (-0.3, 0.15),   # Trailing edge: pressure recovery
    
    # Rear wing pressure taps
    "rw_upper": (-2.3, 0.2), # Upper/suction surface
    "rw_lower": (0.5, 0.1),  # Lower/pressure surface
    "rw_drs": (-1.8, 0.2),   # DRS flap region
    
    # Floor and diffuser
    "floor_fwd": (-0.8, 0.15),  # Forward floor
    "floor_mid": (-2.0, 0.3),   # Mid floor (Venturi)
    "diffuser": (-1.2, 0.2),    # Diffuser exit
    
    # Sidepod and bargeboard
    "sidepod": (-0.5, 0.1),     # Sidepod region
    "barge": (-1.5, 0.25),      # Bargeboard vortex
}


# Channel definitions with sample rates
CHANNEL_DEFINITIONS = {
    # Force Balance (1000 Hz)
    1: ("balance_lift", 1000, "force_balance"),
    2: ("balance_drag", 1000, "force_balance"),
    3: ("balance_side", 1000, "force_balance"),
    4: ("balance_pitch", 1000, "force_balance"),
    5: ("balance_roll", 1000, "force_balance"),
    6: ("balance_yaw", 1000, "force_balance"),
    
    # Component Load Cells (500 Hz)
    7: ("fw_lift", 500, "component_loads"),
    8: ("fw_drag", 500, "component_loads"),
    9: ("rw_lift", 500, "component_loads"),
    10: ("rw_drag", 500, "component_loads"),
    11: ("wheel_fl", 500, "component_loads"),
    12: ("wheel_fr", 500, "component_loads"),
    13: ("wheel_rl", 500, "component_loads"),
    14: ("wheel_rr", 500, "component_loads"),
    
    # Front Wing Pressure (500 Hz)
    15: ("fw_le_1", 500, "fw_pressure"), 16: ("fw_le_2", 500, "fw_pressure"),
    17: ("fw_le_3", 500, "fw_pressure"), 18: ("fw_le_4", 500, "fw_pressure"),
    19: ("fw_mid_1", 500, "fw_pressure"), 20: ("fw_mid_2", 500, "fw_pressure"),
    21: ("fw_mid_3", 500, "fw_pressure"), 22: ("fw_mid_4", 500, "fw_pressure"),
    23: ("fw_te_1", 500, "fw_pressure"), 24: ("fw_te_2", 500, "fw_pressure"),
    25: ("fw_te_3", 500, "fw_pressure"), 26: ("fw_te_4", 500, "fw_pressure"),
    
    # Rear Wing Pressure (500 Hz)
    27: ("rw_upper_1", 500, "rw_pressure"), 28: ("rw_upper_2", 500, "rw_pressure"),
    29: ("rw_upper_3", 500, "rw_pressure"), 30: ("rw_upper_4", 500, "rw_pressure"),
    31: ("rw_lower_1", 500, "rw_pressure"), 32: ("rw_lower_2", 500, "rw_pressure"),
    33: ("rw_lower_3", 500, "rw_pressure"), 34: ("rw_lower_4", 500, "rw_pressure"),
    35: ("rw_drs_1", 500, "rw_pressure"), 36: ("rw_drs_2", 500, "rw_pressure"),
    37: ("rw_drs_3", 500, "rw_pressure"), 38: ("rw_drs_4", 500, "rw_pressure"),
    
    # Floor Pressure (500 Hz)
    39: ("floor_fwd_1", 500, "floor_pressure"), 40: ("floor_fwd_2", 500, "floor_pressure"),
    41: ("floor_fwd_3", 500, "floor_pressure"), 42: ("floor_fwd_4", 500, "floor_pressure"),
    43: ("floor_mid_1", 500, "floor_pressure"), 44: ("floor_mid_2", 500, "floor_pressure"),
    45: ("floor_mid_3", 500, "floor_pressure"), 46: ("floor_mid_4", 500, "floor_pressure"),
    47: ("diffuser_1", 500, "floor_pressure"), 48: ("diffuser_2", 500, "floor_pressure"),
    49: ("diffuser_3", 500, "floor_pressure"), 50: ("diffuser_4", 500, "floor_pressure"),
    
    # Sidepod/Bargeboard Pressure (500 Hz)
    51: ("sidepod_1", 500, "sidepod_pressure"), 52: ("sidepod_2", 500, "sidepod_pressure"),
    53: ("sidepod_3", 500, "sidepod_pressure"), 54: ("sidepod_4", 500, "sidepod_pressure"),
    55: ("barge_1", 500, "barge_pressure"), 56: ("barge_2", 500, "barge_pressure"),
    57: ("barge_3", 500, "barge_pressure"), 58: ("barge_4", 500, "barge_pressure"),
    
    # Velocity (1000 Hz)
    59: ("velocity_x", 1000, "velocity"),
    60: ("velocity_y", 1000, "velocity"),
    61: ("velocity_z", 1000, "velocity"),
    62: ("turbulence", 1000, "velocity"),
    63: ("q_dynamic", 1000, "velocity"),
    64: ("p_static", 1000, "velocity"),
    
    # Environment (100 Hz)
    65: ("temp_tunnel", 100, "environment"),
    66: ("humidity", 100, "environment"),
    67: ("p_baro", 100, "environment"),
    68: ("rho_air", 100, "environment"),
    
    # Position (100 Hz)
    69: ("ride_height_f", 100, "position"),
    70: ("ride_height_r", 100, "position"),
    71: ("pitch_angle", 100, "position"),
    72: ("roll_angle", 100, "position"),
}


class WindTunnelSimulator:
    """
    Physics-based wind tunnel sensor simulator.
    Generates 72 channels with realistic correlations and noise.
    """
    
    def __init__(self, config: RunConfiguration):
        self.config = config
        self.variant = AERO_VARIANTS.get(config.variant, AERO_VARIANTS["baseline"])
        
        # Physical constants
        self.reference_area = 0.54  # m² (60% scale model)
        self.wheelbase = 1.8  # m (60% scale)
        self.front_weight = 200  # N (model weight, front)
        self.rear_weight = 250   # N (model weight, rear)
        
        # Random phases for oscillations (consistent within a run)
        np.random.seed(int(datetime.now().timestamp() * 1000) % (2**31))
        self.phases = {ch: np.random.uniform(0, 2*np.pi) for ch in range(1, 73)}
        
        # Pre-calculate base aerodynamics
        self._calculate_base_aero()
    
    def _calculate_base_aero(self):
        """Calculate base aerodynamic values from config and variant."""
        # Air density from environment
        T_kelvin = self.config.tunnel_temp + 273.15
        self.rho = self.config.tunnel_baro / (287.05 * T_kelvin)
        
        # Dynamic pressure
        V = self.config.tunnel_speed
        self.q = 0.5 * self.rho * V**2
        
        # Forces from coefficients
        Cl = self.variant["Cl"]
        Cd = self.variant["Cd"]
        Cy_per_deg = self.variant["Cy_per_deg"]
        
        # Adjust for angle of attack
        Cl_adjusted = Cl * (1 + 0.05 * self.config.tunnel_aoa)
        
        # Calculate forces (N)
        self.base_lift = -Cl_adjusted * self.q * self.reference_area  # Negative = downforce
        self.base_drag = Cd * self.q * self.reference_area
        self.base_side = Cy_per_deg * self.config.tunnel_yaw * self.q * self.reference_area
        
        # Moments (simplified)
        self.base_pitch = self.base_lift * 0.1  # Nm
        self.base_roll = self.base_side * 0.05
        self.base_yaw = self.base_drag * 0.02
        
        # Component forces
        fw_frac = self.variant["fw_fraction"]
        rw_frac = self.variant["rw_fraction"]
        
        self.fw_lift = fw_frac * abs(self.base_lift)
        self.fw_drag = 0.25 * self.base_drag
        self.rw_lift = rw_frac * abs(self.base_lift)
        self.rw_drag = 0.35 * self.base_drag
        
        # Wheel loads
        balance = self.variant["aero_balance"]
        total_df = abs(self.base_lift)
        self.wheel_fl = (balance * total_df + self.front_weight) / 2
        self.wheel_fr = self.wheel_fl
        self.wheel_rl = ((1 - balance) * total_df + self.rear_weight) / 2
        self.wheel_rr = self.wheel_rl
    
    def _add_noise(self, base_value: float, t: float, channel_id: int,
                   drift_amp: float = 0.02,
                   unsteady_amp: float = 0.03,
                   turbulence_amp: float = 0.01,
                   noise_amp: float = 0.002) -> float:
        """Add realistic noise layers to a base value."""
        phase = self.phases[channel_id]
        
        # Slow drift (thermal effects, tunnel settling) - 0.1 Hz
        drift = drift_amp * base_value * np.sin(2 * np.pi * 0.1 * t + phase)
        
        # Flow unsteadiness (vortex shedding) - 2-8 Hz
        unsteady = unsteady_amp * base_value * np.sin(2 * np.pi * 5 * t + phase * 2)
        
        # High-frequency turbulence - random
        turbulence = turbulence_amp * base_value * np.random.randn()
        
        # Sensor noise
        noise = noise_amp * base_value * np.random.randn()
        
        return base_value + drift + unsteady + turbulence + noise
    
    def _inject_anomaly(self, value: float) -> float:
        """Occasionally inject anomalies for QC testing."""
        r = np.random.random()
        
        # 0.1% chance of spike
        if r < 0.001:
            return value * np.random.uniform(2, 5)
        
        # 0.01% chance of dropout
        if r < 0.0001:
            return 0.0
        
        return value
    
    def _generate_pressure(self, location: str, tap_num: int, t: float) -> float:
        """Generate pressure tap value based on Cp distribution."""
        cp_mean, cp_std = CP_DISTRIBUTIONS.get(location, (-1.0, 0.2))
        
        # Add variation between taps
        cp = cp_mean + (tap_num - 2.5) * cp_std * 0.3
        
        # Convert Cp to absolute pressure
        P = self.config.tunnel_baro + cp * self.q
        
        # Add noise
        channel_id = 15 + tap_num  # Approximate channel ID for phase
        P = self._add_noise(P, t, channel_id, 
                           drift_amp=0.005, unsteady_amp=0.02,
                           turbulence_amp=0.01, noise_amp=0.005)
        
        return self._inject_anomaly(P)
    
    def generate_sample(self, t: float) -> Dict[int, float]:
        """
        Generate all channel values for a single time point.
        
        Args:
            t: Time in seconds from run start
            
        Returns:
            Dictionary mapping channel_id to value
        """
        values = {}
        
        # 1. Force Balance (channels 1-6)
        values[1] = self._inject_anomaly(
            self._add_noise(self.base_lift, t, 1))
        values[2] = self._inject_anomaly(
            self._add_noise(self.base_drag, t, 2))
        values[3] = self._inject_anomaly(
            self._add_noise(self.base_side, t, 3))
        values[4] = self._inject_anomaly(
            self._add_noise(self.base_pitch, t, 4))
        values[5] = self._inject_anomaly(
            self._add_noise(self.base_roll, t, 5))
        values[6] = self._inject_anomaly(
            self._add_noise(self.base_yaw, t, 6))
        
        # 2. Component Loads (channels 7-14)
        values[7] = self._inject_anomaly(
            self._add_noise(self.fw_lift, t, 7))
        values[8] = self._inject_anomaly(
            self._add_noise(self.fw_drag, t, 8))
        values[9] = self._inject_anomaly(
            self._add_noise(self.rw_lift, t, 9))
        values[10] = self._inject_anomaly(
            self._add_noise(self.rw_drag, t, 10))
        values[11] = self._inject_anomaly(
            self._add_noise(self.wheel_fl, t, 11))
        values[12] = self._inject_anomaly(
            self._add_noise(self.wheel_fr, t, 12))
        values[13] = self._inject_anomaly(
            self._add_noise(self.wheel_rl, t, 13))
        values[14] = self._inject_anomaly(
            self._add_noise(self.wheel_rr, t, 14))
        
        # 3. Front Wing Pressure (channels 15-26)
        for i, ch in enumerate(range(15, 19)):
            values[ch] = self._generate_pressure("fw_le", i+1, t)
        for i, ch in enumerate(range(19, 23)):
            values[ch] = self._generate_pressure("fw_mid", i+1, t)
        for i, ch in enumerate(range(23, 27)):
            values[ch] = self._generate_pressure("fw_te", i+1, t)
        
        # 4. Rear Wing Pressure (channels 27-38)
        for i, ch in enumerate(range(27, 31)):
            values[ch] = self._generate_pressure("rw_upper", i+1, t)
        for i, ch in enumerate(range(31, 35)):
            values[ch] = self._generate_pressure("rw_lower", i+1, t)
        for i, ch in enumerate(range(35, 39)):
            values[ch] = self._generate_pressure("rw_drs", i+1, t)
        
        # 5. Floor Pressure (channels 39-50)
        for i, ch in enumerate(range(39, 43)):
            values[ch] = self._generate_pressure("floor_fwd", i+1, t)
        for i, ch in enumerate(range(43, 47)):
            values[ch] = self._generate_pressure("floor_mid", i+1, t)
        for i, ch in enumerate(range(47, 51)):
            values[ch] = self._generate_pressure("diffuser", i+1, t)
        
        # 6. Sidepod/Bargeboard (channels 51-58)
        for i, ch in enumerate(range(51, 55)):
            values[ch] = self._generate_pressure("sidepod", i+1, t)
        for i, ch in enumerate(range(55, 59)):
            values[ch] = self._generate_pressure("barge", i+1, t)
        
        # 7. Velocity (channels 59-64)
        V = self.config.tunnel_speed
        TI = 0.002  # Turbulence intensity 0.2%
        
        values[59] = self._add_noise(V, t, 59, 0.001, 0.005, 0.002, 0.001)
        values[60] = self._add_noise(
            V * np.sin(np.radians(self.config.tunnel_yaw)), t, 60)
        values[61] = self._add_noise(0.0, t, 61, noise_amp=0.1)
        values[62] = self._add_noise(TI * 100, t, 62, 0.1, 0.05, 0.02, 0.01)  # %
        values[63] = self._add_noise(self.q, t, 63, 0.002, 0.01, 0.005, 0.002)
        values[64] = self._add_noise(self.config.tunnel_baro, t, 64, 0.0001, 0.0, 0.0, 0.0001)
        
        # 8. Environment (channels 65-68)
        # Temperature slowly rises during run
        temp = self.config.tunnel_temp + 0.3 * (t / self.config.duration_seconds)
        values[65] = temp + 0.05 * np.random.randn()
        values[66] = self.config.tunnel_humidity + 0.1 * np.random.randn()
        values[67] = self.config.tunnel_baro + 5 * np.random.randn()
        values[68] = self.rho + 0.001 * np.random.randn()
        
        # 9. Position (channels 69-72)
        values[69] = self.config.ride_height_f + 0.05 * np.random.randn()
        values[70] = self.config.ride_height_r + 0.05 * np.random.randn()
        # Pitch from ride heights
        pitch = np.degrees(np.arctan(
            (self.config.ride_height_r - self.config.ride_height_f) / 
            (self.wheelbase * 1000)))
        values[71] = pitch + 0.01 * np.random.randn()
        values[72] = 0.0 + 0.005 * np.random.randn()  # Roll should be ~0
        
        return values
    
    def generate_run(self) -> Generator[Dict, None, None]:
        """
        Generate all samples for a complete run.
        
        Yields:
            Dictionary with keys: channel_id, ts, value
        """
        base_time = datetime.now()
        
        # Get sample rates
        max_rate = 1000  # Hz
        
        # Generate at max rate, decimate for slower channels
        duration = self.config.duration_seconds
        num_samples = int(duration * max_rate)
        
        for i in range(num_samples):
            t = i / max_rate
            ts = base_time + timedelta(seconds=t)
            
            # Generate all channel values
            all_values = self.generate_sample(t)
            
            # Yield samples based on each channel's rate
            for channel_id, value in all_values.items():
                _, rate, _ = CHANNEL_DEFINITIONS[channel_id]
                
                # Decimation: only yield if this time point aligns with channel rate
                samples_per_channel = int(max_rate / rate)
                if i % samples_per_channel == 0:
                    yield {
                        "channel_id": channel_id,
                        "ts": ts,
                        "value": value
                    }
    
    def generate_run_batch(self) -> List[Dict]:
        """Generate all samples as a list (for bulk insert)."""
        return list(self.generate_run())
    
    def get_run_metadata(self) -> Dict:
        """Get run metadata for database insertion."""
        return {
            "name": self.config.name,
            "tunnel_speed": self.config.tunnel_speed,
            "tunnel_aoa": self.config.tunnel_aoa,
            "tunnel_yaw": self.config.tunnel_yaw,
            "tunnel_temp": self.config.tunnel_temp,
            "ride_height_f": self.config.ride_height_f,
            "ride_height_r": self.config.ride_height_r,
            "notes": self.config.notes,
        }


def main():
    """Test the simulator."""
    print("🌪️  Wind Tunnel Sensor Simulator")
    print("=" * 60)
    
    # Create configuration
    config = RunConfiguration(
        name="Test Run - Baseline",
        tunnel_speed=50.0,
        tunnel_aoa=2.0,
        variant="baseline",
        duration_seconds=1.0  # Short test
    )
    
    # Create simulator
    sim = WindTunnelSimulator(config)
    
    print(f"\nConfiguration:")
    print(f"  Variant: {config.variant}")
    print(f"  Speed: {config.tunnel_speed} m/s")
    print(f"  AoA: {config.tunnel_aoa}°")
    print(f"  Duration: {config.duration_seconds}s")
    
    print(f"\nBase Aerodynamics:")
    print(f"  Dynamic pressure (q): {sim.q:.1f} Pa")
    print(f"  Downforce: {abs(sim.base_lift):.1f} N")
    print(f"  Drag: {sim.base_drag:.1f} N")
    print(f"  L/D: {abs(sim.base_lift)/sim.base_drag:.2f}")
    
    print("\nGenerating samples...")
    samples = sim.generate_run_batch()
    
    print(f"  Generated {len(samples):,} samples")
    
    # Count by channel category
    channel_counts = {}
    for s in samples:
        ch = s["channel_id"]
        _, _, category = CHANNEL_DEFINITIONS[ch]
        channel_counts[category] = channel_counts.get(category, 0) + 1
    
    print("\n  Samples by category:")
    for cat, count in sorted(channel_counts.items()):
        print(f"    {cat}: {count:,}")
    
    # Show sample values
    print("\n  Sample values (t=0):")
    t0_samples = {s["channel_id"]: s["value"] for s in samples[:72]}
    print(f"    balance_lift: {t0_samples.get(1, 0):.1f} N")
    print(f"    balance_drag: {t0_samples.get(2, 0):.1f} N")
    print(f"    fw_lift: {t0_samples.get(7, 0):.1f} N")
    print(f"    velocity_x: {t0_samples.get(59, 0):.2f} m/s")
    print(f"    temp_tunnel: {t0_samples.get(65, 0):.2f} °C")
    
    print("\n✅ Simulator working!")


if __name__ == "__main__":
    main()
