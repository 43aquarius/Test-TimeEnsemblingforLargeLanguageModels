Greedy-bias audit: raw evidence
================================

For every question where the greedy decode (temperature 0) disagrees with
the modal answer of the six canonical temperature-0.7 samples, this file
records the raw greedy call (snippet, token usage), the six sampled
answers, the modal answer, and the gold answer. Mechanism labels follow
the paper's Section 5.2 audit.

qwen3.8-max  (greedy 93.3% vs S1 93.3%, 1 off-mode question(s))
  q000: gold=C greedy=A (correct=False, 275pt/3ct tokens)
      samples=['B', 'B', 'B', 'A', 'A', 'B'] -> mode=B (4/6), S1 correct fraction=0.00
      greedy snippet: Answer: A

qwen3.8-omni  (greedy 91.7% vs S1 92.6%, 2 off-mode question(s))
  q001: gold=A greedy=C (correct=False, 191pt/4ct tokens)
      samples=['A', 'C', 'A', 'A', 'C', 'A'] -> mode=A (4/6), S1 correct fraction=0.67
      greedy snippet: Answer: C
  q026: gold=A greedy=C (correct=False, 170pt/6ct tokens)
      samples=['D', 'D', 'C', 'D', 'B', 'A'] -> mode=D (3/6), S1 correct fraction=0.17
      greedy snippet: Answer: (C)

agnes-3.0-flash  (greedy 78.8% vs S1 89.4%, 3 off-mode question(s))
  q006: gold=2 greedy=27 (correct=False, 173pt/1200ct tokens)
      samples=['-24', '2', '2', '2', '2', '2'] -> mode=2 (5/6), S1 correct fraction=0.83
      greedy snippet: To determine how many good days were left in the month, we n ... 
The first 24 days are fully defined.
The last 6 days (25-30) are partially defined by the tota
  q008: gold=C greedy=D (correct=False, 217pt/4ct tokens)
      samples=['C', 'A', 'C', 'C', 'D', 'C'] -> mode=C (4/6), S1 correct fraction=0.67
      greedy snippet: Answer: D
  q017: gold=B greedy=C (correct=False, 207pt/4ct tokens)
      samples=['B', 'B', 'B', 'B', 'B', 'B'] -> mode=B (6/6), S1 correct fraction=1.00
      greedy snippet: Answer: C

agnes-2.5-flash  (greedy 90.2% vs S1 94.3%, 2 off-mode question(s))
  q001: gold=A greedy=C (correct=False, 463pt/431ct tokens)
      samples=['A', 'D', 'A', 'D', 'A', 'A'] -> mode=A (4/6), S1 correct fraction=0.67
      greedy snippet: 

**Answer: C**
  q028: gold=48 greedy=44 (correct=False, 335pt/150ct tokens)
      samples=['48', '48', '48', '48', '48', '48'] -> mode=48 (6/6), S1 correct fraction=1.00
      greedy snippet: 

Let me calculate step by step:

- **Dogs:** 5 dogs × 4 legs each = 20 legs
- **Cats:** 2 cats × 2 legs each = 4 legs
- **Birds:** 10 birds × 2 legs each = 20 
