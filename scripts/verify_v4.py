"""Verify four-factor distribution in factor_daily."""
import os, sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from src.core.db_manager_postgresql import init_db_manager, get_conn, close_db_manager
from sqlalchemy import text
from config.config import SECTOR_ETF

db_url = os.getenv("DATABASE_URL", "")
if not db_url:
    print("[ERROR] DATABASE_URL not set")
    sys.exit(1)

init_db_manager(db_url)
conn = get_conn()
try:
    row = conn.execute(text("""
        SELECT etf_code, z_rsrs, z_flow, z_mom, z_quality, factor, quadrant
        FROM factor_daily
        WHERE preset_id = 'short' AND trade_date = (
            SELECT MAX(trade_date) FROM factor_daily WHERE z_quality IS NOT NULL AND preset_id = 'short'
        )
        ORDER BY factor DESC
    """)).fetchall()

    print(f"Latest four-factor data (short preset, {len(row)} ETFs):")
    hdr = f"{'ETF':14s} {'Name':10s} {'Z_RSRS':8s} {'Z_Flow':8s} {'Z_Mom':8s} {'Z_Qual':8s} {'Factor':8s} {'Q':4s}"
    print(hdr)
    print("-" * 70)
    for r in row:
        name = SECTOR_ETF.get(r[0], r[0])[:10]
        print(f"{r[0]:14s} {name:10s} {float(r[1]):+.3f}  {float(r[2]):+.3f}  {float(r[3]):+.3f}  {float(r[4]):+.3f}  {float(r[5]):+.3f}  {int(r[6]):<4d}")
finally:
    conn.close()
close_db_manager()
