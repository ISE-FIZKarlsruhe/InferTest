# Inconsistency-style test cases (parked)

These 8 constructs test a *violation*, not a derived fact — their `premises.ttl` deliberately breaks the axiom on purpose, and correctness means a reasoner rejects the ontology as inconsistent:

- `asymmetric-property`
- `irreflexive-property`
- `disjoint-classes`
- `disjoint-properties`
- `disjoint-union`
- `complement-of`
- `different-individuals`
- `negative-property-assertion`

Each folder still has its original `premises.ttl` and `expected-inconsistent.flag`, unchanged.

They're intentionally **not** wired into `scripts/enabled-tests.txt` or any of the three scripts right now, because they need handling different from a plain entailment check (a violation can't be merged into a shared ontology alongside other tests without poisoning everything else, and there's no positive triple to check — only "did the reasoner refuse this"). They're kept here to bring back in later.

## Reintroducing them later

1. Move the wanted folder(s) back under `test-cases/`.
2. Add inconsistency-handling logic back into `infertest_lib.py`, `prepare_test_ontology.py`, `validate_entailments.py`, and `run_all_tests.py` (an `is_inconsistency_construct()` check on `expected-inconsistent.flag`, a separate merged output file per violation construct instead of folding it into the shared one, and — for `run_all_tests.py` — checking for `OwlReadyInconsistentOntologyError` instead of running the refutation check). This logic existed in this repo before and can be rebuilt the same way.
