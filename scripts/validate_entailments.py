#!/usr/bin/env python3
"""
InferTest — pipeline step 2: validate expected entailments.

Point this at the ontology file YOUR OWN reasoner produced after being run
over the file prepare_test_ontology.py wrote (i.e. the materialised /
inferred ontology — Turtle, RDF/XML, N-Triples, whatever your pipeline
outputs). For every ENABLED construct (see enabled-tests.txt), this checks
that every triple in its expected-entailments.ttl is actually present in
that file.

This script never runs a reasoner itself — it is a pure triple-membership
check via rdflib — so it works no matter what reasoner produced the
inferred ontology (HermiT, Pellet, ELK, JFact, a SPARQL-based engine, a
triplestore's built-in reasoner, ...).

Usage:
    python validate_entailments.py --inferred /path/to/reasoned-ontology.ttl
    python validate_entailments.py --inferred out.owl --config my-tests.txt
    python validate_entailments.py --inferred out.ttl --only subclass subproperty
"""

import argparse
import sys
from pathlib import Path

try:
    import infertest_lib as lib
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import infertest_lib as lib

try:
    import rdflib
except ImportError:
    print("ERROR: rdflib is not installed. Run: pip install rdflib")
    sys.exit(2)


def check_construct(name: str, inferred_graph: rdflib.Graph):
    expected_graph = lib.parse_rdf_file(lib.construct_dir(name) / lib.ENTAILMENTS_FILE)
    skip = lib.ontology_declaration_triples(expected_graph)

    missing = [
        (s, p, o) for s, p, o in expected_graph
        if (s, p, o) not in skip and (s, p, o) not in inferred_graph
    ]
    return missing


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--inferred", type=Path, required=True,
                         help="Path to the reasoned/materialised ontology your pipeline produced.")
    parser.add_argument("--config", type=Path, default=lib.DEFAULT_CONFIG,
                         help=f"Path to the enabled-tests config file (default: {lib.DEFAULT_CONFIG.name})")
    parser.add_argument("--only", nargs="+", default=None,
                         help="Only check the named construct(s), ignoring --config.")
    args = parser.parse_args()

    if not args.inferred.exists():
        print(f"ERROR: --inferred file not found: {args.inferred}")
        sys.exit(2)

    if args.only:
        all_constructs = set(lib.discover_all_constructs())
        unknown = set(args.only) - all_constructs
        if unknown:
            print(f"ERROR: unknown construct(s): {', '.join(sorted(unknown))}")
            sys.exit(2)
        enabled = sorted(args.only)
    else:
        try:
            enabled = lib.load_enabled_constructs(args.config)
        except (FileNotFoundError, ValueError) as e:
            print(f"ERROR: {e}")
            sys.exit(2)

    if not enabled:
        print("No constructs enabled — nothing to validate.")
        sys.exit(2)

    print(lib.colour(f"InferTest — validating {len(enabled)} construct(s) against {args.inferred}", lib.BOLD))
    print()

    inferred_graph = lib.parse_rdf_file(args.inferred)

    results = []
    for name in enabled:
        missing = check_construct(name, inferred_graph)
        passed = not missing
        results.append((name, passed))
        status = lib.colour("PASS", lib.GREEN) if passed else lib.colour("FAIL", lib.RED)
        print(f"[{status}] {name}")
        for t in missing:
            print(f"       {lib.colour('not entailed: ' + lib.format_triple(t), lib.RED)}")

    print()
    total = len(results)
    passed_count = sum(1 for _, p in results if p)
    failed = [name for name, p in results if not p]

    if failed:
        print(lib.colour(f"{passed_count}/{total} passed. FAILED: {', '.join(failed)}", lib.RED + lib.BOLD))
        sys.exit(1)
    else:
        print(lib.colour(f"{passed_count}/{total} passed.", lib.GREEN + lib.BOLD))
        sys.exit(0)


if __name__ == "__main__":
    main()
