# Expansion set: greedy off-mode audit

Greedy answer falls outside the six-sample modal set. Raw evidence per model in `<model>_offmode.json`.

## agnes-3.0-flash

- complete questions: 119
- off-mode greedy: 15 (12.6%)
- off-mode but greedy correct: 6

| qid | dataset | gold | greedy | greedy ok | mode | share | S-acc |
|---|---|---|---|---|---|---|---|
| e024 | logiqa | D | D | Y | C | 0.67 | 0.17 |
| e035 | sat_math | A | C | N | A | 0.67 | 0.67 |
| e039 | sat_math | A | D | N | B | 0.50 | 0.00 |
| e046 | logiqa | D | B | N | D | 0.50 | 0.50 |
| e067 | logiqa | B | C | N | B | 0.33 | 0.33 |
| e073 | lsat_lr | C | D | N | C | 0.83 | 0.83 |
| e080 | logiqa | C | A | N | C | 0.83 | 0.83 |
| e089 | sat_math | C | C | Y | B | 0.67 | 0.17 |
| e094 | gsm8k | 15 | 15.00 | N | 15 | 0.83 | 0.83 |
| e095 | truthfulqa | A | A | Y | C | 0.67 | 0.33 |
| e098 | sat_math | A | A | Y | B | 0.67 | 0.33 |
| e099 | logiqa | C | D | N | A | 0.50 | 0.17 |
| e108 | gsm8k | 106 | 106 | Y | 106.12 | 0.83 | 0.17 |
| e112 | piqa | 2 | 2 | Y | 1 | 0.67 | 0.33 |
| e116 | piqa | 2 | 1 | N | 2 | 1.00 | 1.00 |

## agnes-2.5-flash

- complete questions: 119
- off-mode greedy: 5 (4.2%)
- off-mode but greedy correct: 1

| qid | dataset | gold | greedy | greedy ok | mode | share | S-acc |
|---|---|---|---|---|---|---|---|
| e024 | logiqa | D | D | Y | A | 0.67 | 0.17 |
| e034 | truthfulqa | B | E | N | D | 0.67 | 0.00 |
| e067 | logiqa | B | C | N | A | 0.67 | 0.17 |
| e073 | lsat_lr | C | D | N | C | 0.67 | 0.67 |
| e103 | truthfulqa | C | B | N | C | 0.83 | 0.83 |

## deepseek-v4.1-flash

- complete questions: 119
- off-mode greedy: 16 (13.5%)
- off-mode but greedy correct: 3

| qid | dataset | gold | greedy | greedy ok | mode | share | S-acc |
|---|---|---|---|---|---|---|---|
| e001 | logiqa | B | C | N | B | 0.50 | 0.50 |
| e006 | logiqa | A | A | Y | B | 0.83 | 0.17 |
| e014 | logiqa | D | A | N | D | 1.00 | 1.00 |
| e017 | lsat_lr | E | B | N | E | 0.83 | 0.83 |
| e024 | logiqa | D | B | N | D | 0.50 | 0.50 |
| e028 | lsat_lr | B | B | Y | C | 0.67 | 0.17 |
| e033 | logiqa | D | C | N | A | 0.67 | 0.33 |
| e060 | logiqa | A | A | Y | D | 0.83 | 0.17 |
| e067 | logiqa | B | A | N | C | 0.50 | 0.33 |
| e070 | logiqa | D | C | N | D | 0.67 | 0.67 |
| e077 | truthfulqa | C | A | N | C | 0.67 | 0.67 |
| e092 | sat_math | C | D | N | C | 0.67 | 0.67 |
| e102 | truthfulqa | D | A | N | D | 1.00 | 1.00 |
| e114 | gsm8k | 48 | 56 | N | 48 | 1.00 | 1.00 |
| e115 | logiqa | D | B | N | D | 0.83 | 0.83 |
| e116 | piqa | 2 | 1 | N | 2 | 0.83 | 0.83 |

## deepseek-v4-pro-0813

- complete questions: 119
- off-mode greedy: 14 (11.8%)
- off-mode but greedy correct: 4

| qid | dataset | gold | greedy | greedy ok | mode | share | S-acc |
|---|---|---|---|---|---|---|---|
| e001 | logiqa | B | B | Y | C | 0.50 | 0.33 |
| e015 | truthfulqa | C | A | N | C | 0.83 | 0.83 |
| e022 | piqa | 2 | 1 | N | 2 | 0.67 | 0.67 |
| e025 | sat_math | C | B | N | D | 0.50 | 0.17 |
| e028 | lsat_lr | B | A | N | C | 0.83 | 0.17 |
| e038 | piqa | 2 | 1 | N | 2 | 0.83 | 0.83 |
| e043 | logiqa | A | A | Y | B | 0.67 | 0.33 |
| e058 | sat_math | B | B | Y | A | 0.83 | 0.17 |
| e067 | logiqa | B | B | Y | C | 0.67 | 0.17 |
| e084 | sat_math | A | D | N | B | 0.67 | 0.17 |
| e091 | gsm8k | 15400 | 6400 | N | 5500 | 0.67 | 0.17 |
| e098 | sat_math | A | B | N | A | 0.83 | 0.83 |
| e112 | piqa | 2 | 1 | N | 2 | 1.00 | 1.00 |
| e115 | logiqa | D | A | N | D | 0.83 | 0.83 |

## qwen3.7-flash

- complete questions: 60
- off-mode greedy: 1 (1.7%)
- off-mode but greedy correct: 0

| qid | dataset | gold | greedy | greedy ok | mode | share | S-acc |
|---|---|---|---|---|---|---|---|
| e053 | lsat_lr | C | D | N | A | 0.67 | 0.33 |

## deepseek-v4-flash-0731

- complete questions: 13
- off-mode greedy: 0 (0.0%)
- off-mode but greedy correct: 0

| qid | dataset | gold | greedy | greedy ok | mode | share | S-acc |
|---|---|---|---|---|---|---|---|
