#!/usr/bin/env python3
"""
InferTest — standalone OWL 2 reasoning conformance test runner.

This is the self-contained option: no external pipeline needed. It runs
every ENABLED construct (see enabled-tests.txt) through a bundled OWL 2 DL
reasoner (HermiT, via owlready2) itself and reports PASS/FAIL.

If you want to plug InferTest into your OWN pipeline / reasoner instead,
use prepare_test_ontology.py + validate_entailments.py — those never run a
reasoner themselves and have no Java dependency.

Every construct folder under test-cases/ contains an expected-entailments.ttl:
every triple in that file must be entailed by premises.ttl.

Note: a separate set of inconsistency/violation-style constructs
(asymmetric-property, disjoint-classes, ...) lives under
inconsistency-test-cases/ and is intentionally not wired into this script
for now.

How entailment is checked
--------------------------
Reasoner CLIs (HermiT, Pellet, ...) print a *summary* of the class/property
hierarchy, not the full materialised closure — e.g. HermiT's instance
realization only reports an individual's *most specific* named types, so a
transitively-implied type (Rex -> Dog -> Animal) never appears verbatim in
its output even though it is genuinely entailed. Scraping that summary text
is therefore not a reliable way to check "was triple X entailed?".

Instead this script uses the standard refutation technique: to check
whether premises.ttl entails a triple T, it adds the *negation* of T to the
ontology (owl:differentFrom for an expected owl:sameAs, an
owl:NegativePropertyAssertion for an expected property assertion, or an
owl:complementOf class for an expected rdf:type) and asks the reasoner to
check consistency. T is entailed if and only if that negated ontology is
INCONSISTENT. This only depends on the reasoner's consistency check, which
every OWL 2 DL reasoner implements and which owlready2 reports reliably via
OwlReadyInconsistentOntologyError — so it works regardless of what a given
reasoner's CLI chooses to print.

If the reasoner fails for some OTHER reason (a Java crash, a parsing
error, an unsupported construct) rather than giving a definite
consistent/inconsistent answer, that construct is reported as ERROR, not
silently counted as PASS or FAIL.

Usage:
    python run_all_tests.py                          # runs enabled-tests.txt selection
    python run_all_tests.py --all                     # runs every construct, ignoring config
    python run_all_tests.py --only subclass domain     # runs only the named construct(s)
    python run_all_tests.py --target /path/to/your-ontology.ttl
    python run_all_tests.py --reasoner pellet
    python run_all_tests.py --verbose

--target merges each test case's premises.ttl with your own ontology
before reasoning, so you can confirm your project's axioms don't break
basic OWL 2 semantics (e.g. an over-eager disjointness or restriction
that swallows one of these constructs).

Requires: pip install owlready2 rdflib   (see requirements.txt)
          a Java runtime on PATH (used by the bundled HermiT/Pellet jars)
"""

import argparse
import io
import sys
from pathlib import Path

try:
    import infertest_lib as lib
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import infertest_lib as lib

try:
    import owlready2
    from owlready2 import World, sync_reasoner, sync_reasoner_pellet
    from owlready2 import OwlReadyInconsistentOntologyError
except ImportError:
    print("ERROR: owlready2 is not installed. Run: pip install -r requirements.txt")
    sys.exit(2)

try:
    import rdflib
    from rdflib import BNode, RDF, OWL
except ImportError:
    print("ERROR: rdflib is not installed. Run: pip install -r requirements.txt")
    sys.exit(2)


class ReasonerFailure(Exception):
    """Raised when the reasoner fails for a reason OTHER than a genuine
    logical inconsistency — a Java crash, a parsing error, an unsupported
    construct, a timeout, etc. Kept distinct from
    OwlReadyInconsistentOntologyError so a broken/crashed reasoner run is
    never silently counted as either PASS or FAIL: it's reported as its own
    ERROR status instead of masquerading as a real result, and it never
    takes down the rest of the run.

    This is a meaningful three-way split, not just defensive
    over-engineering: OWL 2 DL is decidable, so a correct reasoner given a
    syntactically valid OWL 2 DL ontology is guaranteed to terminate with a
    definite consistent/inconsistent verdict. A crash instead of a verdict
    therefore signals a *different* kind of problem (bad input, a reasoner
    bug, resource limits) that deserves its own visible status rather than
    being swallowed into "this construct behaved unexpectedly"."""


def is_inconsistent(graph: rdflib.Graph, reasoner: str, debug: int) -> bool:
    """Load an rdflib graph into a fresh, isolated owlready2 World and run
    the reasoner. Returns True iff the reasoner reports the ontology
    inconsistent; raises ReasonerFailure if the reasoner itself broke."""
    try:
        world = World()
        onto = world.get_ontology("http://infertest.invalid/run")

        buffer = io.BytesIO(graph.serialize(format="nt", encoding="utf-8"))
        buffer.name = "<infertest-merged-graph>"
        onto.load(fileobj=buffer, format="ntriples")

        if reasoner == "pellet":
            sync_reasoner_pellet(world, debug=debug)
        else:
            sync_reasoner(world, debug=debug)
    except OwlReadyInconsistentOntologyError:
        return True
    except owlready2.base.OwlReadyError as e:
        raise ReasonerFailure(str(e)) from e
    return False


def negate_triple(graph: rdflib.Graph, s, p, o):
    """Add the logical negation of triple (s, p, o) to graph in place."""
    if p == RDF.type:
        restriction = BNode()
        graph.add((s, RDF.type, restriction))
        graph.add((restriction, RDF.type, OWL.Class))
        graph.add((restriction, OWL.complementOf, o))
    elif p == OWL.sameAs:
        graph.add((s, OWL.differentFrom, o))
    else:
        assertion = BNode()
        graph.add((assertion, RDF.type, OWL.NegativePropertyAssertion))
        graph.add((assertion, OWL.sourceIndividual, s))
        graph.add((assertion, OWL.assertionProperty, p))
        if isinstance(o, rdflib.Literal):
            # Data property assertion: OWL 2 requires owl:targetValue for a
            # literal target, not owl:targetIndividual.
            graph.add((assertion, OWL.targetValue, o))
        else:
            graph.add((assertion, OWL.targetIndividual, o))


def run_case(name: str, target: Path | None, reasoner: str, debug: int):
    """Returns (name, status, details) where status is 'PASS', 'FAIL', or
    'ERROR' — ERROR meaning the reasoner itself broke (see ReasonerFailure)
    rather than gave a definite consistent/inconsistent answer."""
    case_dir = lib.construct_dir(name)
    entailments_path = case_dir / lib.ENTAILMENTS_FILE

    if not entailments_path.exists():
        return name, "ERROR", [f"no {lib.ENTAILMENTS_FILE} found"]

    graphs = [lib.parse_rdf_file(case_dir / lib.PREMISES_FILE)]
    if target is not None:
        graphs.append(lib.parse_rdf_file(target))
    base_graph = lib.merge_graphs(graphs)

    try:
        # Sanity check: the premises themselves (optionally + --target) must
        # be consistent before we can meaningfully test entailments against
        # them.
        if is_inconsistent(base_graph, reasoner, debug):
            return name, "FAIL", ["premises.ttl (merged with --target, if given) is already "
                                   "INCONSISTENT on its own — this construct expects clean "
                                   "entailments, not a contradiction"]

        expected_graph = lib.parse_rdf_file(entailments_path)
        skip = lib.ontology_declaration_triples(expected_graph)

        missing = []
        for s, p, o in expected_graph:
            if (s, p, o) in skip:
                continue
            refuted_graph = lib.merge_graphs([base_graph])
            negate_triple(refuted_graph, s, p, o)
            if not is_inconsistent(refuted_graph, reasoner, debug):
                missing.append((s, p, o))
    except ReasonerFailure as e:
        return name, "ERROR", [f"reasoner did not return a definite answer: {e}",
                                "(this is neither a confirmed pass nor a confirmed fail — "
                                "rerun with --verbose to see the reasoner's own output)"]

    if missing:
        return name, "FAIL", [f"not entailed: {lib.format_triple(t)}" for t in missing]
    return name, "PASS", []


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=lib.DEFAULT_CONFIG,
                         help=f"Path to the enabled-tests config file (default: {lib.DEFAULT_CONFIG.name})")
    parser.add_argument("--all", action="store_true",
                         help="Run every construct under test-cases/, ignoring --config")
    parser.add_argument("--target", type=Path, default=None,
                         help="Path to your own ontology file; each test case's premises "
                              "are merged with it before reasoning.")
    parser.add_argument("--only", nargs="+", default=None,
                         help="Only run the named test case(s), e.g. --only subclass domain "
                              "(ignores --config/--all)")
    parser.add_argument("--reasoner", choices=["hermit", "pellet"], default="hermit",
                         help="OWL 2 DL reasoner to invoke via owlready2 (default: hermit)")
    parser.add_argument("--verbose", action="store_true",
                         help="Print the underlying reasoner's own output for every check")
    args = parser.parse_args()
    debug = 2 if args.verbose else 0

    if not lib.TEST_CASES_DIR.exists():
        print(f"ERROR: {lib.TEST_CASES_DIR} not found")
        sys.exit(2)

    all_constructs = set(lib.discover_all_constructs())
    if args.only:
        unknown = set(args.only) - all_constructs
        if unknown:
            print(f"ERROR: unknown test case(s): {', '.join(sorted(unknown))}")
            sys.exit(2)
        names = sorted(args.only)
        source = "--only"
    elif args.all:
        names = sorted(all_constructs)
        source = "--all"
    else:
        try:
            names = lib.load_enabled_constructs(args.config)
        except (FileNotFoundError, ValueError) as e:
            print(f"ERROR: {e}")
            sys.exit(2)
        source = str(args.config)

    if not names:
        print("No test cases selected.")
        sys.exit(2)

    print(lib.colour(f"InferTest — running {len(names)} OWL 2 construct test case(s) "
                      f"with {args.reasoner} (selection: {source})", lib.BOLD))
    if args.target:
        print(f"Merging each test case against target ontology: {args.target}")
    print()

    STATUS_COLOUR = {"PASS": lib.GREEN, "FAIL": lib.RED, "ERROR": lib.CYAN}

    results = []
    for name in names:
        result = run_case(name, args.target, args.reasoner, debug)
        results.append(result)
        name, status, details = result
        print(f"[{lib.colour(status, STATUS_COLOUR[status])}] {name}")
        for line in details:
            print(f"       {lib.colour(line, STATUS_COLOUR[status])}")

    print()
    total = len(results)
    passed_count = sum(1 for _, status, _ in results if status == "PASS")
    failed = [name for name, status, _ in results if status == "FAIL"]
    errored = [name for name, status, _ in results if status == "ERROR"]

    if failed or errored:
        summary = f"{passed_count}/{total} passed."
        if failed:
            summary += f" FAILED: {', '.join(failed)}."
        if errored:
            summary += f" ERRORED (no definite answer — investigate, don't treat as pass or fail): {', '.join(errored)}."
        print(lib.colour(summary, lib.RED + lib.BOLD))
        sys.exit(1)
    else:
        print(lib.colour(f"{passed_count}/{total} passed. All selected OWL 2 construct tests PASSED.",
                          lib.GREEN + lib.BOLD))
        sys.exit(0)


if __name__ == "__main__":
    main()
