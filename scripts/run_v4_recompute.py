"""
V4 Full recomputation script.

Runs in order:
1. Database migration (already done via alembic)
2. Financial quality factor computation
3. Multi-factor engine (four-factor with quality)
4. IC analysis
5. Verification output
"""
import os, sys
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from src.core.db_manager_postgresql import init_db_manager, close_db_manager, get_conn
from sqlalchemy import text

db_url = os.getenv("DATABASE_URL", "")
if not db_url:
    print("[ERROR] DATABASE_URL not set")
    sys.exit(1)

init_db_manager(db_url)

print("=" * 60)
print("Step 1/3: Financial Quality Factor Computation")
print("=" * 60)
from src.analysis.financial_factor import compute_and_persist
ff_result = compute_and_persist()
print(f"[OK] Financial factors computed for {len(ff_result)} ETFs")
for code, data in sorted(ff_result.items()):
    from config.config import SECTOR_ETF
    name = SECTOR_ETF.get(code, code)
    print(f"  {name:12s}: F_Quality={data['f_quality']:+.4f}")

print()
print("=" * 60)
print("Step 2/3: Multi-Factor Engine (Four-Factor with Quality)")
print("=" * 60)
from src.analysis.factor_engine import compute_all_factors
n = compute_all_factors()
print(f"[OK] Factor engine: {n} rows upserted")

print()
print("=" * 60)
print("Step 3/3: IC Analysis")
print("=" * 60)
from src.analysis.ic_analyzer import compute_all_ic
n2 = compute_all_ic()
print(f"[OK] IC analysis complete")

print()
print("=" * 60)
print("Verification: Sample factor_daily with z_quality")
print("=" * 60)
conn = get_conn()
try:
    rows = conn.execute(text("""
        SELECT etf_code, trade_date, factor, z_quality, f_quality
        FROM factor_daily
        WHERE z_quality IS NOT NULL AND preset_id = 'short'
        ORDER BY trade_date DESC, factor DESC
        LIMIT 17
    """)).fetchall()
    if not rows:
        print("[WARN] No z_quality data found in factor_daily")
        # Check if quality columns exist
        col_rows = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='factor_daily' AND column_name='z_quality'"
        )).fetchall()
        if col_rows:
            print("[INFO] z_quality column exists but no data — financial factors may not be merged yet")
        else:
            print("[WARN] z_quality column does not exist — migration may not have run")
    else:
        print(f"{'ETF':12s} {'Date':12s} {'Factor':8s} {'Z_Quality':10s} {'F_Quality':10s}")
        print("-" * 52)
        for r in rows:
            print(f"{r[0]:12s} {str(r[1]):12s} {float(r[2]):+.4f}  {float(r[3]):+.4f}    {float(r[4]):+.4f}")
finally:
    conn.close()

close_db_manager()
print()
print("[ALL DONE] V4 recomputation complete")
