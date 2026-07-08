# InferTest
A reusable set of ontology test instances for validating that OWL reasoners produce the expected entailments in NFDIcore-compliant ontologies.


Rather than attempting to validate every possible inference in a knowledge graph, InferTest provides a representative set of test instances that exercise key reasoning capabilities. After reasoning, the inferred ontology is checked for a predefined set of expected entailments.

## How it works

InferTest consists of:

- **NFDI Core-compliant ontology with Test instances** (`infertest.ttl`) that can be imported into an ontology.
- **Expected entailments** describing the inferences that should be produced by a compliant OWL reasoner.
- **Validation scripts** that compare the inferred ontology against the expected entailments. python script? 

The workflow is:

```
Your ontology
      │
      ├── imports infertest.ttl
      │
      ▼
Ontology + test instances
      │
      ▼
Run OWL reasoner
      │
      ▼
Reasoned ontology
      │
      ▼
Validate expected entailments
      │
      ├── All expected entailments found ✔ PASS
      └── Missing entailments ✘ FAIL
```

## Usage

### Option 1 — Import

Add an OWL import to your ontology:

```ttl
owl:imports <infertest.ttl> .
```

### Option 2 — Merge

Merge the InferTest ontology into your ontology using ROBOT:

```bash
robot merge \
    --input myOntology.ttl \
    --input infertest.ttl \
    --output merged.ttl
```

Run your preferred OWL reasoner over the merged ontology.

Finally, execute the validation script to verify that all expected entailments are present.

## Repository structure

```
infertest.ttl          Test instances
expected.ttl           Expected inferred axioms
scripts/               Validation utilities
examples/              Example ontologies
```
