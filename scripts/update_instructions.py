#!/usr/bin/env python3
"""Rewrite instruction sets: direct-answer MCQ (uniform across models), CoT for GSM8K."""

# --- Portable repository root (added during artifact packaging) ---
import os as _os
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import json

data = json.load(open(ROOT + "/data/paraphrases.json"))

INSTR = {
    "gsm8k": {
        "P0": "Solve the problem step by step. End your response with \"Answer: <number>\".",
        "P1": "Work through the problem one step at a time, then conclude with \"Answer: <number>\".",
        "P2": "Reason carefully about the problem and compute the result. The last line must be \"Answer: <number>\".",
        "P3": "Please solve this math problem. Show your reasoning, and finish with \"Answer: <number>\".",
        "P4": "Figure out the solution by working through the calculations. End with \"Answer: <number>\".",
        "P5": "Approach the problem methodically and determine the final value. Terminate your reply with \"Answer: <number>\".",
        "P6": "Think the problem through and calculate the answer. Your response must end with \"Answer: <number>\".",
    },
    "piqa": {
        "P0": "Do not explain your reasoning. Reply with only \"Answer: 1\" if Solution 1 is better, or \"Answer: 2\" if Solution 2 is better.",
        "P1": "Give only your verdict: \"Answer: 1\" or \"Answer: 2\". No explanation.",
        "P2": "Respond with just \"Answer: 1\" or \"Answer: 2\" to indicate the better solution; add nothing else.",
        "P3": "State your pick as \"Answer: 1\" or \"Answer: 2\" with no other text.",
        "P4": "Output only \"Answer: 1\" or \"Answer: 2\", whichever solution you judge better.",
        "P5": "No explanations. Simply end with \"Answer: 1\" or \"Answer: 2\".",
        "P6": "Decide which solution wins and reply with its number alone: \"Answer: 1\" or \"Answer: 2\".",
    },
    "sat_math": {
        "P0": "Do not explain your reasoning. Reply with only the letter of the correct option, in the form \"Answer: <letter>\".",
        "P1": "Give only the letter of the right answer, formatted as \"Answer: <letter>\". No explanation.",
        "P2": "Respond with just the letter of your chosen option using the format \"Answer: <letter>\"; do not add anything else.",
        "P3": "State your final choice as \"Answer: <letter>\" with no other text.",
        "P4": "Output only the letter of the correct option, ending your reply with \"Answer: <letter>\".",
        "P5": "No explanations. Simply conclude with \"Answer: <letter>\" where the letter is your selected option.",
        "P6": "Choose one option and reply with its letter alone, in the form \"Answer: <letter>\".",
    },
    "truthfulqa": {"P0": "Do not explain your reasoning. Reply with only the letter of the correct option, in the form \"Answer: <letter>\"."},
    "lsat_lr": {"P0": "Do not explain your reasoning. Reply with only the letter of the correct option, in the form \"Answer: <letter>\"."},
    "logiqa": {"P0": "Do not explain your reasoning. Reply with only the letter of the correct option, in the form \"Answer: <letter>\"."},
}
data["instructions"] = INSTR
json.dump(data, open(ROOT + "/data/paraphrases.json", "w"), indent=1, ensure_ascii=False)
print("Instructions updated: direct-answer MCQ, CoT GSM8K")
for ds, d in INSTR.items():
    print(f"  {ds}: {len(d)} variants")
