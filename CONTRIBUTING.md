# Contributing

Contributions to verifiers, reference constructions, evaluation adapters and
documentation are welcome.

## Run the checks

```bash
python -m pip install -r requirements-paper.txt
python bench/test_exam.py
python bench/test_verifiers.py
python bench/test_candidate_families.py
python bench/test_trifference_certificates.py
python bench/test_construction_references.py
python bench/test_publication_data.py
```

Include a small valid example and a nearby invalid example when changing a
verifier. For a new compact format, explain why its certificate establishes the
property and exact objective, and add an independent check.

## Propose a construction or reference update

Open an issue with the family, parameters, answer JSON and a source or derivation.
Run the public verifier and include its result. Improvements over published
frontiers need an independent verification and a literature check before being
listed as records. Version-1 references remain fixed; accepted reference updates
belong to a later benchmark version.

## Add a model result

Use the exported call list and the protocol in [Evaluating models](docs/EVALUATING.md).
Report the model version, effort, token budget, generation harness and dates.
Include one scored outcome for each of the 69 distinct instances, including
invalid answers and budget-exhausted calls, and submit the output of
`bench/exam.py score`. Retain infrastructure-attempt metadata and available usage.
Use the first scorable outcome; do not select among responses by answer quality.

## Pull requests

Describe the change and its validation. Keep mathematical changes separate from
formatting changes. Contributions are made under the project's MIT license;
preserve the attribution and terms of any third-party material.
