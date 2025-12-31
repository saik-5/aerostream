"""
Processing Module
=================
Time-series data processing for wind tunnel sensor data.

Modules:
- resampler: Align multi-rate channels to common timebase
- despiker: Remove sensor glitches using MAD algorithm
- aero_metrics: Calculate Cl, Cd, efficiency
- qc_engine: Automated quality control checks
- processor: Pipeline orchestration
"""

from src.processing.resampler import (
    Resampler,
    resample_samples
)

from src.processing.despiker import (
    Despiker,
    DespikeResult,
    despike_channel,
    despike_run
)

from src.processing.aero_metrics import (
    AeroCalculator,
    AeroMetrics,
    AeroCoefficients,
    calculate_aero_metrics
)

from src.processing.qc_engine import (
    QCEngine,
    QCCheck,
    QCSummary,
    QCStatus,
    run_qc
)

from src.processing.processor import (
    RunProcessor,
    ProcessingResult,
    process_run
)

__all__ = [
    # Resampler
    'Resampler',
    'resample_samples',
    
    # Despiker
    'Despiker',
    'DespikeResult',
    'despike_channel',
    'despike_run',
    
    # Aero Metrics
    'AeroCalculator',
    'AeroMetrics',
    'AeroCoefficients',
    'calculate_aero_metrics',
    
    # QC Engine
    'QCEngine',
    'QCCheck',
    'QCSummary',
    'QCStatus',
    'run_qc',
    
    # Processor
    'RunProcessor',
    'ProcessingResult',
    'process_run',
]
