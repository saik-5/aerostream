"""
Processing Pipeline Orchestrator
================================
Orchestrates all processing steps: resample → despike → metrics → QC.
"""

import sys
import os
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass, field
import numpy as np

# Add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.processing.resampler import Resampler, resample_samples
from src.processing.despiker import Despiker, despike_run, DespikeResult
from src.processing.aero_metrics import AeroCalculator, AeroMetrics
from src.processing.qc_engine import QCEngine, QCSummary, QCStatus


@dataclass
class ProcessingResult:
    """Complete processing results for a run."""
    run_id: int
    
    # Resampled data
    timestamps: np.ndarray = field(repr=False)
    channel_data: Dict[int, np.ndarray] = field(default_factory=dict, repr=False)
    
    # Despike results per channel
    despike_results: Dict[int, DespikeResult] = field(default_factory=dict, repr=False)
    total_spikes: int = 0
    
    # Aero metrics
    aero_metrics: Optional[AeroMetrics] = None
    
    # QC summary
    qc_summary: Optional[QCSummary] = None
    
    # Processing metadata
    processing_time_ms: float = 0.0
    original_sample_count: int = 0
    processed_sample_count: int = 0
    
    def to_statistics_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for run_statistics table."""
        stats = {
            'total_samples': self.original_sample_count,
            'valid_samples': self.processed_sample_count,
            'spike_count': self.total_spikes,
        }
        
        if self.aero_metrics:
            stats.update({
                'lift_mean': self.aero_metrics.Cl_mean * 1530 * 1.0,  # Convert back to force
                'drag_mean': self.aero_metrics.Cd_mean * 1530 * 1.0,
                'cl_mean': self.aero_metrics.Cl_mean,
                'cl_std': self.aero_metrics.Cl_std,
                'cd_mean': self.aero_metrics.Cd_mean,
                'cd_std': self.aero_metrics.Cd_std,
                'efficiency': self.aero_metrics.efficiency_mean,
                'aero_balance_pct': self.aero_metrics.balance_mean,
            })
        
        return stats


class RunProcessor:
    """
    Orchestrates the complete processing pipeline for a wind tunnel run.
    
    Pipeline:
    1. Resample → Align all channels to common timebase
    2. Despike → Remove sensor glitches using MAD
    3. Metrics → Calculate Cl, Cd, efficiency
    4. QC → Run quality checks
    """
    
    def __init__(
        self,
        target_hz: float = 100.0,
        despike_threshold: float = 3.5,
        reference_area: float = 1.0
    ):
        """
        Initialize the processor.
        
        Args:
            target_hz: Target sample rate for resampling
            despike_threshold: MAD threshold for spike detection
            reference_area: Reference area for aero coefficients
        """
        self.target_hz = target_hz
        self.despike_threshold = despike_threshold
        self.reference_area = reference_area
        
        self.resampler = Resampler(target_hz=target_hz)
        self.despiker = Despiker(threshold=despike_threshold)
        self.aero_calc = AeroCalculator(reference_area=reference_area)
        self.qc_engine = QCEngine()
    
    def process_from_samples(
        self,
        run_id: int,
        samples: List[Dict],
        expected_sample_count: Optional[int] = None
    ) -> ProcessingResult:
        """
        Process raw sample data through the complete pipeline.
        
        Args:
            run_id: Run identifier
            samples: List of sample dicts with channel_id, ts, value
            expected_sample_count: Optional expected count for QC
            
        Returns:
            ProcessingResult with all processed data
        """
        start_time = datetime.now()
        original_count = len(samples)
        
        # Step 1: Resample to common timebase
        resampled = self.resampler.resample_run(samples)
        
        # Get common time array
        if resampled:
            common_time, aligned_data = self.resampler.align_channels(resampled)
        else:
            common_time = np.array([])
            aligned_data = {}
        
        # Step 2: Despike each channel
        despike_results = {}
        despiked_data = {}
        total_spikes = 0
        
        for channel_id, values in aligned_data.items():
            result = self.despiker.despike(common_time, values)
            despike_results[channel_id] = result
            despiked_data[channel_id] = result.cleaned
            total_spikes += result.spike_count
        
        # Step 3: Calculate aero metrics
        aero_metrics = self.aero_calc.process_run(despiked_data)
        
        # Step 4: Run QC checks
        # Build channel data dict for QC
        channel_data_for_qc = {
            ch_id: (common_time, values)
            for ch_id, values in despiked_data.items()
        }
        
        # Get spike counts per channel
        spike_counts = {
            ch_id: result.spike_count
            for ch_id, result in despike_results.items()
        }
        
        # Calculate expected count if not provided
        if expected_sample_count is None:
            expected_sample_count = original_count
        
        qc_summary = self.qc_engine.run_all_checks(
            channel_data=channel_data_for_qc,
            expected_sample_count=expected_sample_count,
            actual_sample_count=original_count,
            spike_counts=spike_counts,
            expected_dt=1.0 / self.target_hz
        )
        
        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        # Build result
        processed_count = len(common_time) * len(despiked_data) if common_time.size > 0 else 0
        
        return ProcessingResult(
            run_id=run_id,
            timestamps=common_time,
            channel_data=despiked_data,
            despike_results=despike_results,
            total_spikes=total_spikes,
            aero_metrics=aero_metrics,
            qc_summary=qc_summary,
            processing_time_ms=processing_time,
            original_sample_count=original_count,
            processed_sample_count=processed_count
        )
    
    def process_from_database(
        self,
        run_id: int,
        channel_ids: Optional[List[int]] = None
    ) -> ProcessingResult:
        """
        Load data from database and process.
        
        Args:
            run_id: Run ID to process
            channel_ids: Optional list of channels to process
            
        Returns:
            ProcessingResult
        """
        from src.db.connection import execute_query
        
        # Build query
        if channel_ids:
            channel_list = ','.join(str(c) for c in channel_ids)
            query = f"""
                SELECT channel_id, ts, value
                FROM samples
                WHERE run_id = ?
                AND channel_id IN ({channel_list})
                ORDER BY channel_id, ts
            """
        else:
            query = """
                SELECT channel_id, ts, value
                FROM samples
                WHERE run_id = ?
                ORDER BY channel_id, ts
            """
        
        # Execute query
        rows = execute_query(query, (run_id,))
        
        # Convert to sample list
        samples = [
            {'channel_id': row['channel_id'], 'ts': row['ts'], 'value': row['value']}
            for row in rows
        ]
        
        # Get expected count
        count_result = execute_query(
            "SELECT sample_count FROM runs WHERE run_id = ?",
            (run_id,)
        )
        expected_count = count_result[0]['sample_count'] if count_result else None
        
        return self.process_from_samples(run_id, samples, expected_count)
    
    def save_results(self, result: ProcessingResult) -> None:
        """
        Save processing results back to database.
        
        Args:
            result: ProcessingResult to save
        """
        from src.db.operations import save_run_statistics, save_qc_summary, save_qc_result
        from src.db.connection import execute_query, execute_non_query
        
        def _get_or_create_qc_rule_id(rule_code: str, rule_name: str) -> Optional[int]:
            """
            Map a QC rule_code to the DB's qc_rules.rule_id.
            If missing (e.g., older DB), create a minimal rule row so API joins work.
            """
            rows = execute_query(
                "SELECT rule_id FROM qc_rules WHERE rule_code = ?",
                (rule_code,)
            )
            if rows:
                return int(rows[0]["rule_id"])
            
            # Best-effort insert (qc_rules.rule_id is IDENTITY). This keeps demos resilient.
            try:
                execute_non_query(
                    """
                    INSERT INTO qc_rules (rule_name, rule_code, category, check_type, severity, description)
                    VALUES (?, ?, 'custom', 'threshold', 'minor', ?)
                    """,
                    (rule_name, rule_code, f"Auto-created rule for code {rule_code}")
                )
            except Exception:
                return None
            
            rows = execute_query(
                "SELECT rule_id FROM qc_rules WHERE rule_code = ?",
                (rule_code,)
            )
            return int(rows[0]["rule_id"]) if rows else None
        
        # Save statistics
        stats = result.to_statistics_dict()
        save_run_statistics(result.run_id, stats)
        
        # Save QC summary
        if result.qc_summary:
            summary_dict = result.qc_summary.to_dict()
            save_qc_summary(
                run_id=result.run_id,
                overall_status=summary_dict['overall_status'],
                total_checks=summary_dict['total_checks'],
                passed_checks=summary_dict['passed_checks'],
                warning_checks=summary_dict['warning_checks'],
                failed_checks=summary_dict['failed_checks'],
                critical_issues=summary_dict['critical_issues'],
                recommendations=summary_dict['recommendations']
            )
            
            # Save individual QC check results
            for check in result.qc_summary.checks:
                rule_id = _get_or_create_qc_rule_id(check.rule_code, check.rule_name)
                if rule_id is None:
                    # Skip if we cannot map/create the rule; summary is still saved.
                    continue
                
                # Store the threshold most relevant to the check outcome.
                threshold_used = None
                if check.status == QCStatus.FAIL:
                    threshold_used = check.threshold_fail
                elif check.status == QCStatus.WARN:
                    threshold_used = check.threshold_warn
                else:
                    threshold_used = check.threshold_warn or check.threshold_fail
                
                save_qc_result(
                    run_id=result.run_id,
                    rule_id=rule_id,
                    status=check.status.value,
                    measured_value=check.measured_value,
                    threshold_used=threshold_used,
                    details=check.details,
                    channel_id=check.channel_id
                )


def process_run(
    run_id: int,
    samples: List[Dict],
    save_to_db: bool = False
) -> ProcessingResult:
    """
    Convenience function to process a run.
    
    Args:
        run_id: Run identifier
        samples: List of sample dicts
        save_to_db: Whether to save results to database
        
    Returns:
        ProcessingResult
    """
    processor = RunProcessor()
    result = processor.process_from_samples(run_id, samples)
    
    if save_to_db:
        processor.save_results(result)
    
    return result


if __name__ == "__main__":
    # Test the processor
    print("🏎️ Testing Processing Pipeline")
    print("=" * 60)
    
    # Create test data simulating multiple channels at different rates
    np.random.seed(42)
    
    # Simulate 1 second of data
    duration = 1.0
    
    samples = []
    
    # Channel 1: Force balance at 1000 Hz
    n1 = int(duration * 1000)
    for i in range(n1):
        t = i / 1000.0
        v = -3000 + np.sin(2 * np.pi * 5 * t) * 100 + np.random.normal(0, 20)
        samples.append({'channel_id': 1, 'ts': t, 'value': v})
    
    # Channel 2: Drag at 1000 Hz
    for i in range(n1):
        t = i / 1000.0
        v = 600 + np.sin(2 * np.pi * 3 * t) * 20 + np.random.normal(0, 5)
        samples.append({'channel_id': 2, 'ts': t, 'value': v})
    
    # Channel 59: Velocity at 1000 Hz
    for i in range(n1):
        t = i / 1000.0
        v = 50.0 + np.random.normal(0, 0.5)
        samples.append({'channel_id': 59, 'ts': t, 'value': v})
    
    # Add some artificial spikes
    samples[100]['value'] = 0  # Bad data point
    samples[500]['value'] = -10000  # Spike in lift
    
    print(f"Created {len(samples)} samples across 3 channels")
    
    # Process
    processor = RunProcessor(target_hz=100)
    result = processor.process_from_samples(run_id=999, samples=samples)
    
    print(f"\n📊 Processing Results:")
    print(f"  Original samples: {result.original_sample_count:,}")
    print(f"  Processed samples: {result.processed_sample_count:,}")
    print(f"  Processing time: {result.processing_time_ms:.1f}ms")
    print(f"  Total spikes detected: {result.total_spikes}")
    
    print(f"\n🏎️ Aero Metrics:")
    if result.aero_metrics:
        print(f"  Cl: {result.aero_metrics.Cl_mean:.4f} ± {result.aero_metrics.Cl_std:.4f}")
        print(f"  Cd: {result.aero_metrics.Cd_mean:.4f} ± {result.aero_metrics.Cd_std:.4f}")
        print(f"  L/D: {result.aero_metrics.efficiency_mean:.2f}")
    
    print(f"\n🔍 QC Summary:")
    if result.qc_summary:
        print(f"  Overall: {result.qc_summary.overall_status.value.upper()}")
        print(f"  Passed: {result.qc_summary.passed_checks}/{result.qc_summary.total_checks}")
        if result.qc_summary.critical_issues:
            print(f"  Issues: {result.qc_summary.critical_issues}")
    
    print("\n✅ Processing Pipeline working!")
