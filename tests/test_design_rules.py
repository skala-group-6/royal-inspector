"""Design rule (docs/DESIGN.md §1, §7): app UI separates areas by surface tone and spacing, not lines.
Scans web/src except shadcn primitives (components/ui/) and the design comparison page (pages/gallery.tsx shows the old lined look on purpose)."""
import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "web" / "src"
EXEMPT = {WEB / "pages" / "gallery.tsx"}

# divider borders: optional variant prefix(es) + border or border-{t,r,b,l,x,y}, ending the class (so border-r-0, border-border, border-transparent pass)
BORDER = re.compile(r'(?<![\w-])(?:[\w\[\]=:-]+:)?border(?:-[trblxy])?(?=["\'`\s}])')
RULES = {
    "divider border": BORDER,
    "divide-*": re.compile(r'(?<![\w-])divide-[xy]'),
    "Separator": re.compile(r'(?<!DropdownMenu)\bSeparator\b'),
    "inset selection bar": re.compile(r'shadow-\[inset'),
}

def app_files():
    for f in WEB.rglob("*.tsx"):
        if "components/ui" in f.relative_to(WEB).as_posix() or f in EXEMPT:
            continue
        yield f

def test_web_src_exists():
    assert any(app_files()), "web/src not found or empty"

def test_no_lines_in_app_ui():
    hits = []
    for f in app_files():
        for n, line in enumerate(f.read_text().splitlines(), 1):
            if line.lstrip().startswith(("*", "//", "/*")):  # comments may name the rule they follow
                continue
            for name, rx in RULES.items():
                if rx.search(line):
                    hits.append(f"{f.relative_to(WEB)}:{n} {name}: {line.strip()[:100]}")
    assert not hits, "lines found (docs/DESIGN.md §1):\n" + "\n".join(hits)

def test_rule_regex_catches_and_allows():
    assert BORDER.search('className="px-4 border-b py-2"') and BORDER.search('className="border"') and BORDER.search('"md:border-r"')
    for ok in ('"group-data-[side=left]:border-r-0"', '"border-border"', '"border-transparent"', '"rounded-lg"'):
        assert not BORDER.search(ok), ok
    assert not RULES["Separator"].search("<DropdownMenuSeparator />")
