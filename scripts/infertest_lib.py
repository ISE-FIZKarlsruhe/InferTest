"""
InferTest — shared helpers used by prepare_test_ontology.py,
validate_entailments.py and run_all_tests.py.

Only depends on rdflib (no reasoner, no Java) — the actual reasoning is
expected to happen in whatever pipeline step sits between "prepare" and
"validate".
"""

from pathlib import Path

import rdflib

ROOT = Path(__file__).resolve().parent.parent
TEST_CASES_DIR = ROOT / "test-cases"
DEFAULT_CONFIG = Path(__file__).resolve().parent / "enabled-tests.txt"

PREMISES_FILE = "premises.ttl"
ENTAILMENTS_FILE = "expected-entailments.ttl"
INCONSISTENT_FLAG = "expected-inconsistent.flag"


def discover_all_constructs():
    """Every construct folder under test-cases/ that has a premises.ttl."""
    return sorted(
        d.name for d in TEST_CASES_DIR.iterdir()
        if d.is_dir() and (d / PREMISES_FILE).exists()
    )


def load_enabled_constructs(config_path: Path = DEFAULT_CONFIG):
    """Read a config file listing one construct name per line. Blank lines
    and lines starting with '#' are ignored, so constructs can be disabled
    by commenting them out. Returns a sorted list of construct names,
    validated against what actually exists under test-cases/."""
    all_constructs = set(discover_all_constructs())

    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            f"Copy scripts/enabled-tests.txt (or pass --config) to choose which "
            f"constructs to run."
        )

    enabled = []
    unknown = []
    for lineno, raw_line in enumerate(config_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        name = line.split("#", 1)[0].strip()  # allow trailing '# comment'
        if not name:
            continue
        if name not in all_constructs:
            unknown.append((lineno, name))
            continue
        if name not in enabled:
            enabled.append(name)

    if unknown:
        details = ", ".join(f"line {ln}: '{n}'" for ln, n in unknown)
        raise ValueError(
            f"{config_path} references construct(s) that don't exist under "
            f"test-cases/: {details}"
        )

    return sorted(enabled)


def construct_dir(name: str) -> Path:
    return TEST_CASES_DIR / name


def is_entailment_construct(name: str) -> bool:
    return (construct_dir(name) / ENTAILMENTS_FILE).exists()


def is_inconsistency_construct(name: str) -> bool:
    return (construct_dir(name) / INCONSISTENT_FLAG).exists()


def parse_rdf_file(path: Path) -> rdflib.Graph:
    """Parse a Turtle, RDF/XML, N-Triples, etc. file (format guessed from
    its extension)."""
    guessed_format = rdflib.util.guess_format(str(path)) or "turtle"
    g = rdflib.Graph()
    g.parse(path, format=guessed_format)
    return g


def merge_graphs(graphs):
    merged = rdflib.Graph()
    for g in graphs:
        for triple in g:
            merged.add(triple)
    return merged


def ontology_declaration_triples(graph: rdflib.Graph):
    """(s, rdf:type, owl:Ontology) triples — skipped when diffing/checking,
    since every premises/expected file declares its own ontology IRI."""
    return {
        (s, p, o) for s, p, o in graph
        if p == rdflib.RDF.type and o == rdflib.OWL.Ontology
    }


def format_triple(t):
    def short(term):
        text = str(term)
        if "#" in text:
            return text.rsplit("#", 1)[-1]
        return text.rsplit("/", 1)[-1]
    s, p, o = t
    return f"{short(s)} {short(p)} {short(o)}"


RESET = "\033[0m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BOLD = "\033[1m"


def colour(text, code):
    import sys
    if not sys.stdout.isatty():
        return text
    return f"{code}{text}{RESET}"
