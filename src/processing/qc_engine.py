"""
Quality Control Engine
======================
Automated quality checks for wind tunnel sensor data.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class QCStatus(Enum):
    """QC check status."""
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


@dataclass
class QCCheck:
    """Result of a single QC check."""
    rule_id: int
    rule_name: str
    rule_code: str
    status: QCStatus
    measured_value: Optional[float]
    threshold_warn: Optional[float]
    threshold_fail: Optional[float]
    details: str
    channel_id: Optional[int] = None


@dataclass
class QCSummary:
    """Overall QC summary for a run."""
    overall_status: QCStatus
    checks: List[QCCheck] = field(default_factory=list)
    total_checks: int = 0
    passed_checks: int = 0
    warning_checks: int = 0
    failed_checks: int = 0
    skipped_checks: int = 0
    critical_issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    def add_check(self, check: QCCheck):
        """Add a check result and update counts."""
        self.checks.append(check)
        self.total_checks += 1
        
        if check.status == QCStatus.PASS:
            self.passed_checks += 1
        elif check.status == QCStatus.WARN:
            self.warning_checks += 1
        elif check.status == QCStatus.FAIL:
            self.failed_checks += 1
            self.critical_issues.append(f"{check.rule_code}: {check.details}")
        else:
            self.skipped_checks += 1
    
    def finalize(self):
        """Determine overall status based on checks."""
        if self.failed_checks > 0:
            self.overall_status = QCStatus.FAIL
        elif self.warning_checks > 0:
            self.overall_status = QCStatus.WARN
        else:
            self.overall_status = QCStatus.PASS
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for database storage."""
        return {
            'overall_status': self.overall_status.value,
            'total_checks': self.total_checks,
            'passed_checks': self.passed_checks,
            'warning_checks': self.warning_checks,
            'failed_checks': self.failed_checks,
            'skipped_checks': self.skipped_checks,
            'critical_issues': '; '.join(self.critical_issues) if self.critical_issues else '',
            'recommendations': '; '.join(self.recommendations) if self.recommendations else ''
        }


class QCEngine:
    """
    Runs automated quality control checks on wind tunnel data.
    
    Checks include:
    - Missing samples
    - Spike detection (MAD-based)
    - Flatline detection
    - Timestamp gap analysis
    - Range violations
    - Stability checks
    """
    
    # Default thresholds (from qc_rules table)
    DEFAULT_THRESHOLDS = {
        'missing_warn': 1.0,   # % missing samples for warning
        'missing_fail': 5.0,   # % missing samples for failure
        'spike_warn': 0.5,     # % spikes for warning
        'spike_fail': 2.0,     # % spikes for failure
        'stability_warn': 5.0,  # % std deviation for warning
        'stability_fail': 10.0, # % std deviation for failure
        'flatline_duration': 1.0,  # seconds of constant value = flatline
    }
    
    def __init__(self, thresholds: Optional[Dict[str, float]] = None):
        """
        Initialize the QC engine.
        
        Args:
            thresholds: Optional dict of threshold overrides
        """
        self.thresholds = {**self.DEFAULT_THRESHOLDS}
        if thresholds:
            self.thresholds.update(thresholds)
    
    def check_missing_samples(
        self,
        expected_count: int,
        actual_count: int
    ) -> QCCheck:
        """
        Check for missing samples.
        
        Args:
            expected_count: Expected number of samples
            actual_count: Actual number of samples
            
        Returns:
            QCCheck result
        """
        if expected_count == 0:
            return QCCheck(
                rule_id=1,
                rule_name="Missing Data Check",
                rule_code="MISS-DATA",
                status=QCStatus.SKIP,
                measured_value=None,
                threshold_warn=self.thresholds['missing_warn'],
                threshold_fail=self.thresholds['missing_fail'],
                details="No expected count provided"
            )
        
        missing_pct = 100.0 * (expected_count - actual_count) / expected_count
        missing_pct = max(0, missing_pct)  # Clamp to 0 if no missing
        
        if missing_pct >= self.thresholds['missing_fail']:
            status = QCStatus.FAIL
            details = f"{missing_pct:.2f}% samples missing - data may be unusable"
        elif missing_pct >= self.thresholds['missing_warn']:
            status = QCStatus.WARN
            details = f"{missing_pct:.2f}% samples missing - verify data quality"
        else:
            status = QCStatus.PASS
            details = f"{missing_pct:.2f}% samples missing - within tolerance"
        
        return QCCheck(
            rule_id=1,
            rule_name="Missing Data Check",
            rule_code="MISS-DATA",
            status=status,
            measured_value=missing_pct,
            threshold_warn=self.thresholds['missing_warn'],
            threshold_fail=self.thresholds['missing_fail'],
            details=details
        )
    
    def check_spikes(
        self,
        spike_count: int,
        total_samples: int,
        channel_id: Optional[int] = None
    ) -> QCCheck:
        """
        Check for spike percentage.
        
        Args:
            spike_count: Number of detected spikes
            total_samples: Total sample count
            channel_id: Optional channel ID
            
        Returns:
            QCCheck result
        """
        if total_samples == 0:
            return QCCheck(
                rule_id=2,
                rule_name="Spike Detection",
                rule_code="SPIKE-DET",
                status=QCStatus.SKIP,
                measured_value=None,
                threshold_warn=self.thresholds['spike_warn'],
                threshold_fail=self.thresholds['spike_fail'],
                details="No samples to check",
                channel_id=channel_id
            )
        
        spike_pct = 100.0 * spike_count / total_samples
        
        if spike_pct >= self.thresholds['spike_fail']:
            status = QCStatus.FAIL
            details = f"{spike_pct:.2f}% spikes detected ({spike_count} samples) - sensor issue"
        elif spike_pct >= self.thresholds['spike_warn']:
            status = QCStatus.WARN
            details = f"{spike_pct:.2f}% spikes detected - review sensor calibration"
        else:
            status = QCStatus.PASS
            details = f"{spike_pct:.3f}% spikes detected - within tolerance"
        
        return QCCheck(
            rule_id=2,
            rule_name="Spike Detection",
            rule_code="SPIKE-DET",
            status=status,
            measured_value=spike_pct,
            threshold_warn=self.thresholds['spike_warn'],
            threshold_fail=self.thresholds['spike_fail'],
            details=details,
            channel_id=channel_id
        )
    
    def check_flatline(
        self,
        timestamps: np.ndarray,
        values: np.ndarray,
        channel_id: Optional[int] = None
    ) -> QCCheck:
        """
        Check for flatline (sensor stuck at constant value).
        
        Args:
            timestamps: Time array
            values: Value array
            channel_id: Optional channel ID
            
        Returns:
            QCCheck result
        """
        if len(values) < 10:
            return QCCheck(
                rule_id=3,
                rule_name="Flatline Detection",
                rule_code="FLAT-DET",
                status=QCStatus.SKIP,
                measured_value=None,
                threshold_warn=None,
                threshold_fail=self.thresholds['flatline_duration'],
                details="Insufficient data for flatline check",
                channel_id=channel_id
            )
        
        # Find runs of identical values
        diff = np.diff(values)
        is_constant = np.abs(diff) < 1e-10
        
        # Find longest run of constants
        max_run = 0
        current_run = 0
        for i, constant in enumerate(is_constant):
            if constant:
                current_run += 1
                max_run = max(max_run, current_run)
            else:
                current_run = 0
        
        # Calculate duration of longest run
        if len(timestamps) > 1:
            dt = np.median(np.diff(timestamps))
            max_duration = max_run * dt
        else:
            max_duration = 0
        
        threshold = self.thresholds['flatline_duration']
        
        if max_duration >= threshold:
            status = QCStatus.FAIL
            details = f"Flatline detected: {max_duration:.2f}s of constant value - sensor failure"
        else:
            status = QCStatus.PASS
            details = f"No significant flatlines detected (max: {max_duration:.3f}s)"
        
        return QCCheck(
            rule_id=3,
            rule_name="Flatline Detection",
            rule_code="FLAT-DET",
            status=status,
            measured_value=max_duration,
            threshold_warn=None,
            threshold_fail=threshold,
            details=details,
            channel_id=channel_id
        )
    
    def check_timestamp_gaps(
        self,
        timestamps: np.ndarray,
        expected_dt: float
    ) -> QCCheck:
        """
        Check for timestamp gaps (data loss).
        
        Args:
            timestamps: Time array
            expected_dt: Expected time step (seconds)
            
        Returns:
            QCCheck result
        """
        if len(timestamps) < 2:
            return QCCheck(
                rule_id=4,
                rule_name="Timestamp Gaps",
                rule_code="TS-GAP",
                status=QCStatus.SKIP,
                measured_value=None,
                threshold_warn=None,
                threshold_fail=None,
                details="Insufficient timestamps for gap check"
            )
        
        # Calculate actual time differences
        dt = np.diff(timestamps)
        
        # Find gaps (> 2x expected dt)
        gap_threshold = expected_dt * 2.0
        gaps = dt[dt > gap_threshold]
        num_gaps = len(gaps)
        
        if num_gaps > 5:
            status = QCStatus.FAIL
            max_gap = np.max(gaps)
            details = f"{num_gaps} gaps found (max: {max_gap:.3f}s) - check network/DAQ"
        elif num_gaps > 0:
            status = QCStatus.WARN
            max_gap = np.max(gaps)
            details = f"{num_gaps} gaps found (max: {max_gap:.3f}s)"
        else:
            status = QCStatus.PASS
            details = "No timestamp gaps detected"
        
        return QCCheck(
            rule_id=4,
            rule_name="Timestamp Gaps",
            rule_code="TS-GAP",
            status=status,
            measured_value=float(num_gaps),
            threshold_warn=1,
            threshold_fail=5,
            details=details
        )
    
    def check_stability(
        self,
        values: np.ndarray,
        channel_id: Optional[int] = None,
        channel_name: str = "channel"
    ) -> QCCheck:
        """
        Check signal stability (coefficient of variation).
        
        Args:
            values: Value array
            channel_id: Optional channel ID
            channel_name: Channel name for reporting
            
        Returns:
            QCCheck result
        """
        if len(values) < 10:
            return QCCheck(
                rule_id=5,
                rule_name="Stability Check",
                rule_code="STAB-CHK",
                status=QCStatus.SKIP,
                measured_value=None,
                threshold_warn=self.thresholds['stability_warn'],
                threshold_fail=self.thresholds['stability_fail'],
                details=f"Insufficient data for {channel_name} stability check",
                channel_id=channel_id
            )
        
        mean_val = np.mean(values)
        std_val = np.std(values)
        
        # Coefficient of variation (%)
        if np.abs(mean_val) > 1e-10:
            cv = 100.0 * std_val / np.abs(mean_val)
        else:
            cv = 0.0  # Can't calculate CV if mean is ~0
        
        if cv >= self.thresholds['stability_fail']:
            status = QCStatus.FAIL
            details = f"{channel_name}: CV={cv:.2f}% - signal unstable"
        elif cv >= self.thresholds['stability_warn']:
            status = QCStatus.WARN
            details = f"{channel_name}: CV={cv:.2f}% - higher than expected variation"
        else:
            status = QCStatus.PASS
            details = f"{channel_name}: CV={cv:.2f}% - stable"
        
        return QCCheck(
            rule_id=5,
            rule_name="Stability Check",
            rule_code="STAB-CHK",
            status=status,
            measured_value=cv,
            threshold_warn=self.thresholds['stability_warn'],
            threshold_fail=self.thresholds['stability_fail'],
            details=details,
            channel_id=channel_id
        )
    
    def check_range(
        self,
        values: np.ndarray,
        min_val: float,
        max_val: float,
        channel_id: Optional[int] = None,
        channel_name: str = "channel"
    ) -> QCCheck:
        """
        Check if values are within expected sensor range.
        
        Args:
            values: Value array
            min_val: Minimum expected value
            max_val: Maximum expected value
            channel_id: Optional channel ID
            channel_name: Channel name for reporting
            
        Returns:
            QCCheck result
        """
        if len(values) == 0:
            return QCCheck(
                rule_id=6,
                rule_name="Sensor Range Check",
                rule_code="RANGE-CHK",
                status=QCStatus.SKIP,
                measured_value=None,
                threshold_warn=None,
                threshold_fail=None,
                details=f"No data for {channel_name} range check",
                channel_id=channel_id
            )
        
        actual_min = np.min(values)
        actual_max = np.max(values)
        
        out_of_range = (actual_min < min_val) or (actual_max > max_val)
        
        if out_of_range:
            status = QCStatus.FAIL
            details = f"{channel_name}: Range [{actual_min:.2f}, {actual_max:.2f}] exceeds [{min_val:.2f}, {max_val:.2f}]"
        else:
            status = QCStatus.PASS
            details = f"{channel_name}: Range [{actual_min:.2f}, {actual_max:.2f}] within limits"
        
        return QCCheck(
            rule_id=6,
            rule_name="Sensor Range Check",
            rule_code="RANGE-CHK",
            status=status,
            measured_value=None,
            threshold_warn=None,
            threshold_fail=None,
            details=details,
            channel_id=channel_id
        )
    
    def run_all_checks(
        self,
        channel_data: Dict[int, Tuple[np.ndarray, np.ndarray]],
        expected_sample_count: int,
        actual_sample_count: int,
        spike_counts: Optional[Dict[int, int]] = None,
        expected_dt: float = 0.001
    ) -> QCSummary:
        """
        Run all QC checks on a run's data.
        
        Args:
            channel_data: Dict mapping channel_id to (timestamps, values)
            expected_sample_count: Expected total samples
            actual_sample_count: Actual sample count
            spike_counts: Optional dict of spike counts per channel
            expected_dt: Expected time step (seconds)
            
        Returns:
            QCSummary with all check results
        """
        summary = QCSummary(overall_status=QCStatus.PASS)
        
        # 1. Missing samples check (run-level)
        summary.add_check(
            self.check_missing_samples(expected_sample_count, actual_sample_count)
        )
        
        # Per-channel checks
        for channel_id, (timestamps, values) in channel_data.items():
            
            # 2. Spike check
            if spike_counts and channel_id in spike_counts:
                summary.add_check(
                    self.check_spikes(
                        spike_counts[channel_id],
                        len(values),
                        channel_id
                    )
                )
            
            # 3. Flatline check
            summary.add_check(
                self.check_flatline(timestamps, values, channel_id)
            )
            
            # 4. Timestamp gaps (only check first channel once)
            if channel_id == list(channel_data.keys())[0]:
                summary.add_check(
                    self.check_timestamp_gaps(timestamps, expected_dt)
                )
        
        # Add recommendations based on failures
        if summary.failed_checks > 0:
            summary.recommendations.append("Review sensor connections and calibration")
            summary.recommendations.append("Consider repeating test if critical data affected")
        
        if summary.warning_checks > 0:
            summary.recommendations.append("Data may require manual review before use")
        
        summary.finalize()
        return summary


def run_qc(
    channel_data: Dict[int, Tuple[np.ndarray, np.ndarray]],
    expected_sample_count: int,
    actual_sample_count: int,
    spike_counts: Optional[Dict[int, int]] = None
) -> QCSummary:
    """
    Convenience function to run QC checks.
    
    Args:
        channel_data: Dict mapping channel_id to (timestamps, values)
        expected_sample_count: Expected total samples
        actual_sample_count: Actual sample count
        spike_counts: Optional dict of spike counts per channel
        
    Returns:
        QCSummary
    """
    engine = QCEngine()
    return engine.run_all_checks(
        channel_data,
        expected_sample_count,
        actual_sample_count,
        spike_counts
    )


if __name__ == "__main__":
    # Test the QC engine
    print("🔍 Testing QC Engine")
    print("=" * 50)
    
    # Create test data
    n_samples = 1000
    t = np.linspace(0, 10, n_samples)
    
    # Good channel
    good_values = np.sin(2 * np.pi * 0.5 * t) + np.random.normal(0, 0.1, n_samples)
    
    # Channel with spikes
    spikey_values = good_values.copy()
    spikey_values[100] = 10.0  # Add spike
    
    # Channel with flatline
    flatline_values = good_values.copy()
    flatline_values[200:300] = 0.0  # 1 second flatline
    
    channel_data = {
        1: (t, good_values),
        2: (t, spikey_values),
        3: (t, flatline_values)
    }
    
    spike_counts = {1: 0, 2: 5, 3: 0}
    
    # Run QC
    engine = QCEngine()
    summary = engine.run_all_checks(
        channel_data=channel_data,
        expected_sample_count=1000,
        actual_sample_count=950,  # Simulate 5% missing
        spike_counts=spike_counts,
        expected_dt=0.01
    )
    
    print(f"\nOverall Status: {summary.overall_status.value.upper()}")
    print(f"Total Checks: {summary.total_checks}")
    print(f"  Passed: {summary.passed_checks}")
    print(f"  Warnings: {summary.warning_checks}")
    print(f"  Failed: {summary.failed_checks}")
    
    print("\nCheck Details:")
    for check in summary.checks:
        icon = {"pass": "✅", "warn": "⚠️", "fail": "❌", "skip": "⏭️"}[check.status.value]
        print(f"  {icon} {check.rule_code}: {check.details}")
    
    if summary.critical_issues:
        print("\nCritical Issues:")
        for issue in summary.critical_issues:
            print(f"  ❌ {issue}")
    
    if summary.recommendations:
        print("\nRecommendations:")
        for rec in summary.recommendations:
            print(f"  💡 {rec}")
    
    print("\n✅ QC Engine working!")
