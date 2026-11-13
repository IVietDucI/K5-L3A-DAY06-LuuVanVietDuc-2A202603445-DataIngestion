# Think Python benchmark

20 questions: Q01-Q15 dev (Chapters 1-3), Q16-Q20 test (Chapter 4).
Four explicit chapter filters: Q04, Q09, Q16, Q20 (two in test).
Questions/answers are Vietnamese; source evidence is English. Keep this cross-language setting identical across A/B/C.
Physical PDF pages are numbered from 1. Evidence is a literal span from NFC/whitespace-normalized pypdf extraction.
Gold source/page/answer/evidence are evaluation data only; never send them as retrieval input.
Only question text and its explicit filter may enter retrieval. C applies filters; A/B do not.

## Split and limitations
Split is fixed before retrieval runs. Chapter-level holdout reduces near-duplicate passages, but all chapters belong to one book and share function-related concepts. Five test questions are a small illustrative sample. Preparing gold is allowed; do not tune retrieval from test results.

## Selection rule fixed before test
Compare configurations on dev Evidence Hit@3, then dev Hit@1; if tied, prefer lower measured embedding/storage resources. Use test only for final reporting. Report coherence, metadata correctness and human grounding separately; do not infer human scores from string matching.

## Gold verification and alternatives
The author must read each question, answer, physical page and extracted quote to confirm meaning. Script checks presence, not semantic sufficiency. alternative_gold starts empty, not a claim that answers occur on only one page. During manual review, record any equally valid source/page/evidence alternatives and apply them consistently to all strategies without changing the query/split/filter or tuning from test.

## Rebuild and audit
Run python scripts/build_benchmark.py from starter. It validates the PDF against data/manifest.json and refuses to overwrite an existing benchmark. Commit the script, questions, this note and the .sha256 file before retrieval. Never commit .env.
