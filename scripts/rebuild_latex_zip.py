#!/usr/bin/env python3
"""Rebuild ONLY latex_source.zip for v1.6.0 from the synced github_repo/paper.
Other three assets (pdf/docx/supp zip) verified correct already."""
import os, zipfile

REPO = "/home/z/my-project/github_repo"
OUT = "/home/z/my-project/release_assets"
DEST = os.path.join(OUT, "latex_source.zip")

INCLUDE_DIRS = {"sections", "tables", "figures"}
INCLUDE_ROOT = {"main.tex", "refs.bib"}

n = 0
with zipfile.ZipFile(DEST, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    paper_root = os.path.join(REPO, "paper")
    for root, dirs, files in os.walk(paper_root):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        rel_dir = os.path.relpath(root, paper_root)
        for f in sorted(files):
            if rel_dir == "." and f not in INCLUDE_ROOT:
                continue  # skip stray root-level tex duplicates & build products
            if rel_dir != "." and rel_dir.split(os.sep)[0] not in INCLUDE_DIRS:
                continue
            p = os.path.join(root, f)
            z.write(p, os.path.join("latex_source", os.path.relpath(p, paper_root)))
            n += 1
print(f"rebuilt {DEST} ({os.path.getsize(DEST)/1024:.0f} KB, {n} files)")

# verify
z = zipfile.ZipFile(DEST)
c = z.read("latex_source/tables/tab_expand.tex").decode()
assert "Pro-0813" in c and "476" in c, "tab_expand.tex still old!"
c2 = z.read("latex_source/sections/results.tex").decode()
assert "Pro-0813" in c2, "results.tex missing v4-pro!"
print("verified: zip tables + sections are the four-model version")
