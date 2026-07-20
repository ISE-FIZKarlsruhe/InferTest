#!/usr/bin/env python3
"""
InferTest — pipeline step 1: prepare test ontologies.

Merges the premises.ttl of every ENABLED construct (see enabled-tests.txt)
into a single ontology file, optionally together with your own ontology.
Feed the output file(s) into whatever OWL 2 DL reasoner your own pipeline
already uses (Protege, ROBOT, TopBraid, Stardog, GraphDB, owlready2, ...).
Once your pipeline has produced the reasoned/materialised ontology, check
it with validate_entailments.py.

This script never runs a reasoner itself — it only reads and writes RDF
files (via rdflib), so it has no Java dependency and works with any
downstream reasoning tool.

Entailment-style constructs (most of them) are all merged into ONE output
file, because they're meant to coexist peacefully.

Inconsistency-style constructs (asymmetric-property, disjoint-classes, ...)
are each written to their OWN separate file instead. They contain a
deliberate logical violation on purpose — merging one into the main file
would make the WHOLE ontology unsatisfiable and most reasoners either
refuse to produce any output at all or report every other test as failed
too. Run each one through your reasoner in isolation: your pipeline should
observe that reasoning run fail / report inconsistency. If it completes
cleanly, that construct test has failed.

Usage:
    python prepare_test_ontology.py
    python prepare_test_ontology.py --target /path/to/your-ontology.ttl
    python prepare_test_ontology.py --config my-tests.txt --output-dir build
    python prepare_test_ontology.py --format xml   # write RDF/XML instead of Turtle
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


RDFLIB_FORMAT_EXT = {
    "turtle": "ttl",
    "xml": "owl",
    "nt": "nt",
    "n3": "n3",
    "json-ld": "jsonld",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=lib.DEFAULT_CONFIG,
                         help=f"Path to the enabled-tests config file (default: {lib.DEFAULT_CONFIG.name})")
    parser.add_argument("--target", type=Path, default=None,
                         help="Your own ontology file to merge every test case's premises into.")
    parser.add_argument("--output-dir", type=Path, default=Path("build"),
                         help="Directory to write the merged ontology file(s) into (default: ./build)")
    parser.add_argument("--output", type=str, default=None,
                         help="Filename (within --output-dir) for the main merged entailment-test "
                              "ontology (default: infertest-merged.<ext>)")
    parser.add_argument("--format", choices=sorted(RDFLIB_FORMAT_EXT), default="turtle",
                         help="RDF serialization to write (default: turtle)")
    args = parser.parse_args()

    try:
        enabled = lib.load_enabled_constructs(args.config)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}")
        sys.exit(2)

    if not enabled:
        print(f"No constructs enabled in {args.config} — nothing to prepare.")
        sys.exit(2)

    entailment_constructs = [c for c in enabled if lib.is_entailment_construct(c)]
    inconsistency_constructs = [c for c in enabled if lib.is_inconsistency_construct(c)]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    ext = RDFLIB_FORMAT_EXT[args.format]

    target_graph = lib.parse_rdf_file(args.target) if args.target else None

    written = []

    # --- one merged file for every entailment-style construct ---
    if entailment_constructs:
        graphs = ([target_graph] if target_graph is not None else [])
        for name in entailment_constructs:
            graphs.append(lib.parse_rdf_file(lib.construct_dir(name) / lib.PREMISES_FILE))
        merged = lib.merge_graphs(graphs)

        out_name = args.output or f"infertest-merged.{ext}"
        out_path = args.output_dir / out_name
        merged.serialize(destination=str(out_path), format=args.format)
        written.append(("merged entailment test ontology", out_path, entailment_constructs))

    # --- one separate file per inconsistency-style construct ---
    inconsistency_files = {}
    for name in inconsistency_constructs:
        graphs = ([target_graph] if target_graph is not None else [])
        graphs.append(lib.parse_rdf_file(lib.construct_dir(name) / lib.PREMISES_FILE))
        merged = lib.merge_graphs(graphs)

        out_path = args.output_dir / f"infertest-{name}-expect-inconsistent.{ext}"
        merged.serialize(destination=str(out_path), format=args.format)
        inconsistency_files[name] = str(out_path)
        written.append((f"'{name}' inconsistency check", out_path, [name]))

    print(f"InferTest — prepared {len(enabled)} construct(s) from {args.config}\n")
    for label, path, constructs in written:
        print(f"  {label}: {path}")
        for c in constructs:
            print(f"    - {c}")
    print()
    print("Next steps:")
    if entailment_constructs:
        out_name = args.output or f"infertest-merged.{ext}"
        print(f"  1. Run your OWL 2 DL reasoner over {args.output_dir / out_name} and save/export its")
        print("     materialised (inferred) ontology.")
        print(f"  2. python validate_entailments.py --inferred <your-reasoned-file> --config {args.config}")
    if inconsistency_constructs:
        print("  3. For each *-expect-inconsistent file, run it through your reasoner in isolation.")
        print("     That run should FAIL / report the ontology inconsistent. A clean, successful run")
        print("     means that construct's test has FAILED.")


if __name__ == "__main__":
    main()
