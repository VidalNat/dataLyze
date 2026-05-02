"""
modules/analysis/runners.py -- Legacy compatibility shim.
=========================================================

⚠️  This file is intentionally EMPTY of logic.

Historical note:
    In earlier versions of Lytrize, all runner functions lived in this one
    file. They have since been extracted into individual modules for clarity:

        descriptive.py  -- run_descriptive()
        statistical.py  -- run_statistical()
        distribution.py -- run_distribution()
        correlation.py  -- run_correlation()
        categorical.py  -- run_categorical()
        pie_chart.py    -- run_pie_chart()
        time_series.py  -- run_time_series()
        data_quality.py -- run_data_quality()
        outlier.py      -- run_outlier()

This file is kept so any external code that may import from runners.py
continues to work. All imports are re-exported from here.

CONTRIBUTING: add new runners in their own dedicated file, then register
them in modules/analysis/__init__.py -- not here.
"""

# Re-export all runners for backwards compatibility.
from modules.analysis.descriptive  import run_descriptive   # noqa: F401
from modules.analysis.statistical  import run_statistical   # noqa: F401
from modules.analysis.distribution import run_distribution  # noqa: F401
from modules.analysis.correlation  import run_correlation   # noqa: F401
from modules.analysis.categorical  import run_categorical   # noqa: F401
from modules.analysis.pie_chart    import run_pie_chart     # noqa: F401
from modules.analysis.time_series  import run_time_series   # noqa: F401
from modules.analysis.data_quality import run_data_quality  # noqa: F401
from modules.analysis.outlier      import run_outlier       # noqa: F401
