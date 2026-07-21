# InferTest

A generic, reusable suite of OWL 2 reasoning test cases — one small, self-contained ontology per OWL 2 construct (subclass, subproperty, domain, range, inverse, symmetric, transitive, property chains, cardinality, `hasKey`, and more) — for validating that an OWL 2 DL reasoner produces the expected entailments before you trust it inside a real ontology-modelling project.

Rather than trying to validate every possible inference in your knowledge graph, InferTest gives you a small, representative test per construct, a config file to control which ones are active, and scripts to plug the whole thing into **your own** pipeline (whatever reasoner you already use) — plus a self-contained option if you don't have a pipeline yet.

## How it works

InferTest consists of:

- **`test-cases/<construct>/premises.ttl`** — a minimal, self-contained OWL 2 ontology that exercises exactly one construct (e.g. `rdfs:subClassOf`, `owl:TransitiveProperty`, `owl:hasKey`, `owl:propertyChainAxiom`, ...).
- **`test-cases/<construct>/expected-entailments.ttl`** — the triples a conformant OWL 2 DL reasoner *must* derive from that premises file. Present for constructs that produce new facts.
- **`test-cases/<construct>/expected-inconsistent.flag`** — present instead, for constructs whose defining behaviour is that a violation makes the ontology *inconsistent* (e.g. `owl:AsymmetricProperty`, `owl:disjointWith`, `owl:NegativePropertyAssertion`).
- **`scripts/enabled-tests.txt`** — the one place to control which constructs are actually in play. One name per line; comment a line out with `#` to disable it. Every script below reads this file by default.

Each test case is independent and uses uniquely prefixed names (`Subclass_Dog`, `Transitive_PartOf`, ...) so any combination of them can be merged together without colliding.

## Two ways to run it

### Option A — plug into your own pipeline (recommended)

Two small, reasoner-agnostic scripts (pure Python + [rdflib](https://rdflib.readthedocs.io/), no Java, no bundled reasoner) that sit at either end of *your* existing reasoning step:

```
python scripts/prepare_test_ontology.py [--target your-ontology.ttl]
                │
                ▼
   build/infertest-merged.ttl        <- enabled entailment-test constructs (+ your ontology)
   build/infertest-<construct>-expect-inconsistent.ttl   <- one per enabled violation-test construct
                │
                ▼
     >>> run YOUR OWN reasoner over these files, however your pipeline already does that <<<
     (Protégé "Save inferred axioms", ROBOT `robot reason`, a triplestore's built-in reasoner,
      owlready2, a CI step, ...) and save the materialised/inferred ontology it produces
                │
                ▼
python scripts/validate_entailments.py --inferred <your-reasoned-file>
                │
                ├── every expected triple present -> PASS, exit 0
                └── something missing              -> FAIL, exit 1 (CI-friendly)
```

`prepare_test_ontology.py` never runs a reasoner — it just merges Turtle/RDF files. `validate_entailments.py` never runs a reasoner either — it just checks that the expected triples are present in whatever file you point it at. Both only need `rdflib`. Inconsistency-style constructs are handled differently — see the dedicated section below.

```bash
pip install rdflib
python scripts/prepare_test_ontology.py --target your-ontology.ttl
# ... run your reasoner ...
python scripts/validate_entailments.py --inferred path/to/your-reasoners-output.ttl
```

### Option B — standalone, no pipeline needed

`scripts/run_all_tests.py` is self-contained: it bundles its own OWL 2 DL reasoner (HermiT, via [owlready2](https://owlready2.readthedocs.io/)) and does the merge-reason-check cycle itself, for every enabled construct.

```bash
pip install -r scripts/requirements.txt   # owlready2 + rdflib; also requires a Java runtime on PATH
python scripts/run_all_tests.py
```

Exits `0` and prints `All selected OWL 2 construct tests PASSED` if everything behaved as expected; exits `1` and lists the failing construct(s) otherwise.

```bash
python scripts/run_all_tests.py --target your-ontology.ttl   # merge your ontology in too
python scripts/run_all_tests.py --all                        # ignore enabled-tests.txt, run everything
python scripts/run_all_tests.py --only subclass domain        # run specific construct(s)
python scripts/run_all_tests.py --reasoner pellet             # use Pellet instead of HermiT
python scripts/run_all_tests.py --verbose                     # print the reasoner's own output
```

It checks entailment by **refutation** rather than by scraping reasoner output: to check whether `premises.ttl` entails triple `T`, it adds `T`'s logical negation (`owl:differentFrom` for an expected `owl:sameAs`, an `owl:NegativePropertyAssertion` for an expected property assertion, an `owl:complementOf` class for an expected `rdf:type`) and checks that the result is inconsistent. This is necessary because reasoner CLIs print summaries, not full closures — e.g. HermiT's instance realization reports only an individual's most-specific type, and never prints inferred `owl:sameAs` merges at all, so scraping that text misses real entailments.

## Output

Both `validate_entailments.py` and `run_all_tests.py` print one `[PASS]`/`[FAIL]` line per construct (missing triples listed underneath any failure), then a single summary line + exit code for the whole run:

```
[PASS] class-assertion
[FAIL] subclass
       not entailed: Subclass_Rex type Subclass_Animal

1/2 passed. FAILED: subclass
```

Exit `0` = all passed, `1` = something failed (CI-friendly) — but the failed construct(s) and their missing triples are always named, never just a bare pass/fail.

## Inconsistency-style constructs

Eight constructs test a *violation*, not a derived fact: `asymmetric-property`, `irreflexive-property`, `disjoint-classes`, `disjoint-properties`, `disjoint-union`, `complement-of`, `different-individuals`, `negative-property-assertion`. Their `premises.ttl` breaks the axiom on purpose — e.g. `disjoint-classes` asserts one individual as a member of two classes declared `owl:disjointWith` each other — so correctness means the reasoner *rejects* the ontology. There's no new triple to check, only "did this become inconsistent." That's why these folders have `expected-inconsistent.flag` instead of `expected-entailments.ttl`, and each script treats them differently:

- **`prepare_test_ontology.py`** never adds one to the shared `infertest-merged.ttl` — one contradiction there would make the *entire* file unsatisfiable and mask every other construct's result. Each instead gets its own file: `build/infertest-<construct>-expect-inconsistent.ttl` (just `--target` + that one `premises.ttl`).
- **You** run your reasoner over each of those files individually, outside this repo. A correct run should fail / report the ontology inconsistent. A clean, successful run means that construct's test has **failed** — your reasoner (or your own ontology's axioms) didn't catch the violation.
- **`validate_entailments.py`** skips them entirely — it only prints a one-line note listing which ones were skipped. There's no positive triple to look for once an ontology is inconsistent.
- **`run_all_tests.py`** (standalone option) checks them itself, since it already drives HermiT: it loads `premises.ttl`, runs the reasoner, and expects an `OwlReadyInconsistentOntologyError` — PASS if raised, FAIL if the reasoner reports the ontology consistent.

## Controlling which constructs are active

Edit `scripts/enabled-tests.txt`:

```
subclass
subproperty
inverse-properties
class-assertion
object-property-assertion
data-property-assertion

# domain
# range
# equivalent-classes
# ... (29 more, all commented out by default)
```

Uncomment a line to bring that construct into `prepare_test_ontology.py`, `validate_entailments.py`, and `run_all_tests.py`'s default selection — no other changes needed. All three scripts also accept `--config <path>` to use a different selection file (e.g. per-project or per-CI-stage configs), and `--only <name> ...` to override the config entirely for a one-off run.

## Repository structure

```
test-cases/<construct>/
    premises.ttl                  Minimal ontology exercising one OWL 2 construct
    expected-entailments.ttl      Triples that must be entailed (most constructs)
    expected-inconsistent.flag    Present instead, if the construct is violation-based

scripts/
    enabled-tests.txt             Which constructs are active — edit this first
    infertest_lib.py              Shared helpers (config parsing, RDF I/O) used by all 3 scripts
    prepare_test_ontology.py      Pipeline step 1 — merge (no reasoner, rdflib only)
    validate_entailments.py       Pipeline step 2 — check (no reasoner, rdflib only)
    run_all_tests.py              Standalone option — bundles HermiT via owlready2
    requirements.txt              Python dependencies
```

## Adding or modifying a test case

Each construct lives in its own folder under `test-cases/`, so it can be edited independently without touching anything else:

1. Create `test-cases/<construct-name>/premises.ttl` — declare classes/properties/individuals prefixed with the construct name (e.g. `MyConstruct_Foo`) to avoid collisions with other test cases when several are merged together.
2. Add either:
   - `expected-entailments.ttl` with the triples that must be derivable, or
   - `expected-inconsistent.flag` (plain text, any content) if the construct is a violation/consistency test.
3. Add a line for it to `scripts/enabled-tests.txt` (or pass `--only <construct-name>` for a one-off run).
4. Check it: `python scripts/run_all_tests.py --only <construct-name>`, or run it through the prepare/validate pipeline.
