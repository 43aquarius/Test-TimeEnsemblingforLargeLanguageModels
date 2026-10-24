#!/usr/bin/env python3
"""v1.7.0 surgery: move greedy-paraphrase / MMLU-Pro / CoT subsections from
results.tex into a new sections/appendix.tex (with app: labels added), keeping
results.tex well-formed. Idempotent guard: aborts if appendix.tex exists."""
import os

RES = "/home/z/my-project/paper/sections/results.tex"
APP = "/home/z/my-project/paper/sections/appendix.tex"
if os.path.exists(APP):
    raise SystemExit("appendix.tex already exists; refusing to re-run")

txt = open(RES).read()
START = "\\subsection{Isolating the prompt-space effect: greedy paraphrases}"
END = "\\subsection{Budget efficiency: early stopping and adaptive allocation}"
i, j = txt.index(START), txt.index(END)
moved = txt[i:j].rstrip() + "\n"
rest = txt[:i] + txt[j:]

# appendix labels: add app: aliases alongside existing sec: labels
moved = moved.replace(
    "\\subsection{Isolating the prompt-space effect: greedy paraphrases}\n\\label{sec:greedypara}",
    "\\section{Greedy paraphrases: isolating the prompt-space effect}\n\\label{app:greedypara}\n\\label{sec:greedypara}")
moved = moved.replace(
    "\\subsection{Harder tasks: the MMLU-Pro probe}\n\\label{sec:mmlupro}",
    "\\section{Harder tasks: the MMLU-Pro probe}\n\\label{app:mmlupro}\n\\label{sec:mmlupro}")
moved = moved.replace(
    "\\subsection{Answering mode: direct answer versus chain of thought}\n\\label{sec:cot}",
    "\\section{Answering mode: direct answer versus chain of thought}\n\\label{app:cot}\n\\label{sec:cot}")
assert moved.count("\\label{app:") == 3, moved.count("\\label{app:")

header = ("% Appendix for v1.7.0: follow-up conditions, moved out of the main\n"
          "% results section. Labels sec:greedypara / sec:mmlupro / sec:cot are\n"
          "% preserved so existing cross-references keep resolving.\n\n")
open(APP, "w").write(header + moved)
open(RES, "w").write(rest)
print(f"moved {len(moved)} chars to appendix.tex; results.tex now {len(rest)} chars")
print("appendix sections:", [l for l in moved.splitlines() if l.startswith("\\section{")])
