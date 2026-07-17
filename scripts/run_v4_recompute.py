"""
Full recomputation script (factor engine + IC analysis).

Simplified 2026-07-01: the financial-quality step was removed along with the
Quality factor; the script now runs the two live stages. Use the live
``/api/analysis/recompute`` endpoint for the same thing from the UI.
"""
import os, sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from src.core.db_manager_postgresql import init_db_manager, close_db_manager

db_url = os.getenv("DATABASE_URL", "")
if not db_url:
    print("[ERROR] DATABASE_URL not set")
    sys.exit(1)

init_db_manager(db_url)

print("=" * 60)
print("Step 1/2: Multi-Factor Engine")
print("=" * 60)
from src.analysis.factor_engine import compute_all_factors
n = compute_all_factors()
print(f"[OK] Factor engine: {n} rows upserted")

print()
print("=" * 60)
print("Step 2/2: IC Analysis")
print("=" * 60)
from src.analysis.ic_analyzer import compute_all_ic
compute_all_ic()
print("[OK] IC analysis complete")

close_db_manager()
print()
print("[ALL DONE] recomputation complete")
