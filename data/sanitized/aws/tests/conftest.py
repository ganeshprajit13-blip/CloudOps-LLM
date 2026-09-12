"""
Pytest configuration for RCA Deep Research Agent tests.
"""

import sys
from pathlib import Path

# Add src directory to path for imports
src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))

# Pytest fixtures can be added here
