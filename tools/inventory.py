"""Step 1: scan every sheet of every xlsx in data/raw and write a one-page inventory.
Read-only. Does not print cell values beyond short header labels."""
import sys, csv, re
from pathlib import Path
import openpyxl

RAW = Path("data/raw"); OUT = Path("data/inventory")
rows = []

def is_textish(v):
    return isinstance(v, str) and 0 < len(v.strip()) <= 30

for f in sorted(RAW.glob("*.xlsx")):
    wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
    for ws in wb.worksheets:
        max_r, max_c = ws.max_row or 0, ws.max_column or 0
        # scan first 15 rows to guess header line: first row where >=60% of non-empty cells are short text and >=3 cells filled
        header_row, header_vals, first_rows = None, [], []
        for i, r in enumerate(ws.iter_rows(min_row=1, max_row=min(15, max_r), values_only=True), start=1):
            vals = [v for v in r if v not in (None, "")]
            first_rows.append(len(vals))
            if header_row is None and len(vals) >= 3 and sum(is_textish(v) for v in vals) / len(vals) >= 0.6:
                header_row, header_vals = i, [str(v).strip() for v in vals]
        # count non-empty data rows (sample-limited for huge sheets)
        n_nonempty = 0
        for r in ws.iter_rows(min_row=1, max_row=max_r, values_only=True):
            if any(v not in (None, "") for v in r): n_nonempty += 1
        merged = len(getattr(ws, "merged_cells", []).ranges) if hasattr(ws, "merged_cells") else "?"
        rows.append(dict(file=f.name, sheet=ws.title, max_row=max_r, max_col=max_c, nonempty_rows=n_nonempty,
                         header_row=header_row, n_header_cols=len(header_vals),
                         first15_fill=",".join(map(str, first_rows)),
                         header_preview=" | ".join(header_vals[:12]) + (" ..." if len(header_vals) > 12 else "")))
        print(f"{f.name[:20]:20} | {ws.title[:24]:24} | rows={max_r:>7} nonempty={n_nonempty:>7} cols={max_c:>3} | hdr@{header_row} ({len(header_vals)}) | {rows[-1]['header_preview'][:90]}", flush=True)
    wb.close()

with open(OUT / "sheet_inventory.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print(f"\n{len(rows)} sheets -> {OUT/'sheet_inventory.csv'}")
