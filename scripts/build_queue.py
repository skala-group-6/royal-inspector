"""Step 3.95: build the review queue for a period = rule rows (score order) + model top-M unflagged + random p% of unflagged.
Usage: build_queue.py --from 2025-03-01 --to 2025-03-31 [--p-random 0.10] [--m-model 20] [--seed 42] [--min-random 10] [--force]. Uses DATABASE_URL (current tenant)."""
import sys, os, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--from", dest="pf", required=True); ap.add_argument("--to", dest="pt", required=True)
ap.add_argument("--p-random", type=float, default=0.10); ap.add_argument("--m-model", type=int, default=20); ap.add_argument("--seed", type=int, default=42)
ap.add_argument("--min-random", type=int, default=10); ap.add_argument("--force", action="store_true")
a = ap.parse_args()
from app import service as s
r = s.build_queue(a.pf, a.pt, a.p_random, a.m_model, a.seed, a.min_random, a.force)
print(f"queue {r['queue_id']} {r['period_from']}~{r['period_to']}: rule {r['n_rule']:,} · model {r['n_model']} · random {r['n_random']} (pool {r['n_pool_unflagged']:,}) · kept reviewed {r['kept_reviewed']}")
