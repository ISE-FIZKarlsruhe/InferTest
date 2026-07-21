#!/usr/bin/env python3
"""
InferTest — pipeline step 1: prepare a test ontology.

Merges the premises.ttl of every ENABLED construct (see enabled-tests.txt)
into a single ontology file, optionally together with your own ontology.
Feed the output file into whatever OWL 2 DL reasoner your own pipeline
already uses (Protege, ROBOT, TopBraid, Stardog, GraphDB, owlready2, ...).
Once your pipeline has produced the reasoned/materialised ontology, check
it with validate_entailments.py.

This script never runs a reasoner itself — it only reads and writes RDF
files (via rdflib), so it has no Java dependency and works with any
downstream reasoning tool.

Note: only entailment-style constructs are handled here. A separate set of
inconsistency/violation-style constructs (asymmetric-property,
disjoint-classes, ...) lives under inconsistency-test-cases/ and is
intentionally not wired into this pipeline for now.

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
                         help="Directory to write the merged ontology file into (default: ./build)")
    parser.add_argument("--output", type=str, default=None,
                         help="Filename (within --output-dir) for the merged ontology "
                              "(default: infertest-merged.<ext>)")
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

    args.output_dir.mkdir(parents=True, exist_ok=True)
    ext = RDFLIB_FORMAT_EXT[args.format]

    graphs = []
    if args.target:
        graphs.append(lib.parse_rdf_file(args.target))
    for name in enabled:
        graphs.append(lib.parse_rdf_file(lib.construct_dir(name) / lib.PREMISES_FILE))
    merged = lib.merge_graphs(graphs)

    out_name = args.output or f"infertest-merged.{ext}"
    out_path = args.output_dir / out_name
    merged.serialize(destination=str(out_path), format=args.format)

    print(f"InferTest — prepared {len(enabled)} construct(s) from {args.config}\n")
    print(f"  merged test ontology: {out_path}")
    for name in enabled:
        print(f"    - {name}")
    print()
    print("Next steps:")
    print(f"  1. Run your OWL 2 DL reasoner over {out_path} and save/export its materialised")
    print("     (inferred) ontology.")
    print(f"  2. python validate_entailments.py --inferred <your-reasoned-file> --config {args.config}")


if __name__ == "__main__":
    main()
