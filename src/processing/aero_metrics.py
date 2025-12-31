"""
Aerodynamic Metrics Module
==========================
Calculates derived aerodynamic coefficients from force and pressure data.
"""

import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class AeroCoefficients:
    """Aerodynamic coefficients for a time instant or averaged."""
    Cl: float  # Lift coefficient
    Cd: float  # Drag coefficient
    Cy: float  # Side force coefficient
    Cm: float  # Pitching moment coefficient
    efficiency: float  # L/D ratio (|Cl|/Cd)
    aero_balance: float  # Front downforce percentage


@dataclass 
class AeroMetrics:
    """Complete aerodynamic metrics for a run."""
    # Force coefficients (time arrays)
    Cl: np.ndarray = field(repr=False)
    Cd: np.ndarray = field(repr=False)
    Cy: np.ndarray = field(repr=False)
    
    # Moment coefficients
    Cm_pitch: np.ndarray = field(repr=False)
    Cm_roll: np.ndarray = field(repr=False)
    Cm_yaw: np.ndarray = field(repr=False)
    
    # Derived metrics
    efficiency: np.ndarray = field(repr=False)  # L/D ratio
    aero_balance: np.ndarray = field(repr=False)  # Front %
    
    # Statistics
    Cl_mean: float = 0.0
    Cl_std: float = 0.0
    Cd_mean: float = 0.0
    Cd_std: float = 0.0
    efficiency_mean: float = 0.0
    balance_mean: float = 0.0
    
    def __repr__(self):
        return (
            f"AeroMetrics(Cl={self.Cl_mean:.4f}±{self.Cl_std:.4f}, "
            f"Cd={self.Cd_mean:.4f}±{self.Cd_std:.4f}, "
            f"L/D={self.efficiency_mean:.2f}, "
            f"Balance={self.balance_mean:.1f}%)"
        )


class AeroCalculator:
    """
    Calculates aerodynamic coefficients from force balance data.
    
    Uses standard non-dimensional coefficients:
    Cl = Lift / (q * A)
    Cd = Drag / (q * A)
    where q = 0.5 * rho * V^2 (dynamic pressure)
    """
    
    # Standard air density at sea level (kg/m³)
    RHO_STD = 1.225
    
    def __init__(
        self,
        reference_area: float = 1.0,
        wheelbase: float = 3.6,
        scale_factor: float = 0.6
    ):
        """
        Initialize the aero calculator.
        
        Args:
            reference_area: Reference area for coefficients (m²)
            wheelbase: Model wheelbase for moment reference (m)
            scale_factor: Wind tunnel model scale (e.g., 0.6 = 60%)
        """
        self.reference_area = reference_area
        self.wheelbase = wheelbase
        self.scale_factor = scale_factor
    
    def calculate_dynamic_pressure(
        self,
        velocity: np.ndarray,
        air_density: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """
        Calculate dynamic pressure q = 0.5 * rho * V^2.
        
        Args:
            velocity: Freestream velocity array (m/s)
            air_density: Optional air density array (kg/m³)
            
        Returns:
            Dynamic pressure array (Pa)
        """
        if air_density is None:
            air_density = self.RHO_STD
        
        return 0.5 * air_density * velocity ** 2
    
    def calculate_coefficients(
        self,
        lift: np.ndarray,
        drag: np.ndarray,
        side_force: np.ndarray,
        dynamic_pressure: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Calculate force coefficients.
        
        Args:
            lift: Lift force array (N) - negative = downforce
            drag: Drag force array (N)
            side_force: Side force array (N)
            dynamic_pressure: Dynamic pressure array (Pa)
            
        Returns:
            Tuple of (Cl, Cd, Cy) arrays
        """
        q_A = dynamic_pressure * self.reference_area
        
        # Avoid division by zero
        q_A = np.where(q_A > 0, q_A, np.nan)
        
        Cl = lift / q_A
        Cd = drag / q_A
        Cy = side_force / q_A
        
        return Cl, Cd, Cy
    
    def calculate_moments(
        self,
        pitch_moment: np.ndarray,
        roll_moment: np.ndarray,
        yaw_moment: np.ndarray,
        dynamic_pressure: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Calculate moment coefficients.
        
        Args:
            pitch_moment: Pitching moment array (Nm)
            roll_moment: Rolling moment array (Nm)
            yaw_moment: Yawing moment array (Nm)
            dynamic_pressure: Dynamic pressure array (Pa)
            
        Returns:
            Tuple of (Cm_pitch, Cm_roll, Cm_yaw) arrays
        """
        q_A_L = dynamic_pressure * self.reference_area * self.wheelbase
        
        # Avoid division by zero
        q_A_L = np.where(q_A_L > 0, q_A_L, np.nan)
        
        Cm_pitch = pitch_moment / q_A_L
        Cm_roll = roll_moment / q_A_L
        Cm_yaw = yaw_moment / q_A_L
        
        return Cm_pitch, Cm_roll, Cm_yaw
    
    def calculate_efficiency(
        self,
        Cl: np.ndarray,
        Cd: np.ndarray
    ) -> np.ndarray:
        """
        Calculate aerodynamic efficiency (L/D ratio).
        Uses absolute Cl to handle downforce (negative lift).
        
        Args:
            Cl: Lift coefficient array
            Cd: Drag coefficient array
            
        Returns:
            Efficiency array (|Cl|/Cd)
        """
        # Avoid division by zero
        Cd_safe = np.where(Cd > 0, Cd, np.nan)
        return np.abs(Cl) / Cd_safe
    
    def calculate_aero_balance(
        self,
        front_downforce: np.ndarray,
        rear_downforce: np.ndarray
    ) -> np.ndarray:
        """
        Calculate aerodynamic balance (front downforce percentage).
        
        Args:
            front_downforce: Front axle downforce (N, positive down)
            rear_downforce: Rear axle downforce (N, positive down)
            
        Returns:
            Front percentage array (0-100)
        """
        total = front_downforce + rear_downforce
        total_safe = np.where(total > 0, total, np.nan)
        return 100.0 * front_downforce / total_safe
    
    def process_run(
        self,
        channel_data: Dict[int, np.ndarray],
        channel_mapping: Optional[Dict[str, int]] = None
    ) -> AeroMetrics:
        """
        Process a run's channel data to calculate all aero metrics.
        
        Args:
            channel_data: Dict mapping channel_id to value array
            channel_mapping: Optional mapping of channel names to IDs
                            Defaults assume standard channel IDs
        
        Returns:
            AeroMetrics object with all calculated values
        """
        # Default channel mapping (from init.sql)
        if channel_mapping is None:
            channel_mapping = {
                'lift': 1,         # balance_lift
                'drag': 2,         # balance_drag
                'side': 3,         # balance_side
                'pitch': 4,        # balance_pitch
                'roll': 5,         # balance_roll
                'yaw': 6,          # balance_yaw
                'fw_lift': 7,      # Front wing lift
                'rw_lift': 9,      # Rear wing lift
                'velocity': 59,    # velocity_x
                'q_dynamic': 63,   # Dynamic pressure
                'rho': 68,         # Air density
            }
        
        # Get required channels with fallbacks
        lift = channel_data.get(channel_mapping.get('lift', 1), np.array([0.0]))
        drag = channel_data.get(channel_mapping.get('drag', 2), np.array([0.0]))
        side = channel_data.get(channel_mapping.get('side', 3), np.array([0.0]))
        
        pitch = channel_data.get(channel_mapping.get('pitch', 4), np.array([0.0]))
        roll = channel_data.get(channel_mapping.get('roll', 5), np.array([0.0]))
        yaw = channel_data.get(channel_mapping.get('yaw', 6), np.array([0.0]))
        
        velocity = channel_data.get(channel_mapping.get('velocity', 59), np.array([50.0]))
        
        # Calculate dynamic pressure
        rho = channel_data.get(channel_mapping.get('rho', 68), None)
        if rho is None:
            rho = self.RHO_STD
        q = self.calculate_dynamic_pressure(velocity, rho)
        
        # Calculate force coefficients
        Cl, Cd, Cy = self.calculate_coefficients(lift, drag, side, q)
        
        # Calculate moment coefficients
        Cm_pitch, Cm_roll, Cm_yaw = self.calculate_moments(pitch, roll, yaw, q)
        
        # Calculate efficiency
        efficiency = self.calculate_efficiency(Cl, Cd)
        
        # Calculate aero balance (estimate from front/rear wing if available)
        fw_lift = channel_data.get(channel_mapping.get('fw_lift', 7), None)
        rw_lift = channel_data.get(channel_mapping.get('rw_lift', 9), None)
        
        if fw_lift is not None and rw_lift is not None:
            # Use actual front/rear split
            aero_balance = self.calculate_aero_balance(
                np.abs(fw_lift), np.abs(rw_lift)
            )
        else:
            # Estimate: assume 45% front for typical race car
            aero_balance = np.full_like(Cl, 45.0)
        
        # Calculate statistics (ignoring NaN)
        Cl_mean = float(np.nanmean(Cl))
        Cl_std = float(np.nanstd(Cl))
        Cd_mean = float(np.nanmean(Cd))
        Cd_std = float(np.nanstd(Cd))
        efficiency_mean = float(np.nanmean(efficiency))
        balance_mean = float(np.nanmean(aero_balance))
        
        return AeroMetrics(
            Cl=Cl,
            Cd=Cd,
            Cy=Cy,
            Cm_pitch=Cm_pitch,
            Cm_roll=Cm_roll,
            Cm_yaw=Cm_yaw,
            efficiency=efficiency,
            aero_balance=aero_balance,
            Cl_mean=Cl_mean,
            Cl_std=Cl_std,
            Cd_mean=Cd_mean,
            Cd_std=Cd_std,
            efficiency_mean=efficiency_mean,
            balance_mean=balance_mean
        )


def calculate_aero_metrics(
    channel_data: Dict[int, np.ndarray],
    reference_area: float = 1.0
) -> AeroMetrics:
    """
    Convenience function to calculate aero metrics.
    
    Args:
        channel_data: Dict mapping channel_id to value array
        reference_area: Reference area for coefficients
        
    Returns:
        AeroMetrics object
    """
    calculator = AeroCalculator(reference_area=reference_area)
    return calculator.process_run(channel_data)


if __name__ == "__main__":
    # Test the aero calculator
    print("🏎️ Testing Aero Metrics Calculator")
    print("=" * 50)
    
    # Create test data
    n_samples = 100
    
    # Simulate typical motorsport wind tunnel data
    velocity = np.full(n_samples, 50.0)  # 50 m/s
    dynamic_pressure = 0.5 * 1.225 * velocity ** 2  # ~1530 Pa
    
    # Downforce ~3000N, Drag ~600N for typical race car at 50 m/s (60% scale)
    lift = -3000 + np.random.normal(0, 50, n_samples)  # Negative = downforce
    drag = 600 + np.random.normal(0, 10, n_samples)
    side = np.random.normal(0, 20, n_samples)
    
    # Create channel data dict
    channel_data = {
        1: lift,        # balance_lift
        2: drag,        # balance_drag
        3: side,        # balance_side
        4: np.zeros(n_samples),  # pitch moment
        5: np.zeros(n_samples),  # roll moment
        6: np.zeros(n_samples),  # yaw moment
        59: velocity,   # velocity_x
    }
    
    # Calculate metrics
    calculator = AeroCalculator(reference_area=1.0)
    metrics = calculator.process_run(channel_data)
    
    print(f"\nResults:")
    print(f"  Cl (mean): {metrics.Cl_mean:.4f} ± {metrics.Cl_std:.4f}")
    print(f"  Cd (mean): {metrics.Cd_mean:.4f} ± {metrics.Cd_std:.4f}")
    print(f"  L/D ratio: {metrics.efficiency_mean:.2f}")
    print(f"  Aero balance: {metrics.balance_mean:.1f}% front")
    
    print(f"\n{metrics}")
    print("\n✅ Aero Metrics Calculator working!")
