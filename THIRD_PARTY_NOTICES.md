# Sources and third-party notices

The [MIT license](LICENSE) covers the project's original software and documentation.
Third-party files retain their original notices and terms.

## Mathematical constructions and reference values

The benchmark uses published mathematical results, numerical tables and verified
construction witnesses. Their sources are recorded in
[the paper bibliography](bench/paper/references.bib), the frozen files in
[`bench/frontiers`](bench/frontiers), and the reference data in
[`bench/data`](bench/data). Please retain these attributions when reusing the data.

Sources include the La Jolla Covering Repository, published cap-set and Schur
constructions, and reference constructions for Shannon and trifference codes.
Each reference's status and mathematical bound are described in the paper.

The three covering witnesses in `bench/frontier_audits/2026-09-17-covering`
and their copies in `bench/data/reference_witnesses/`
come from Daniel M. Gordon's [La Jolla Coverings Repository](https://doi.org/10.5281/zenodo.19735294),
under CC BY 4.0. Their metadata identify the original contributors. Point labels
were changed from `1..v` to `0..v-1`; the blocks are otherwise unchanged.
The archive's notice is retained in [LICENSES/CC-BY-4.0-LJCR.txt](LICENSES/CC-BY-4.0-LJCR.txt).

## Paper templates

The ICLR style and bibliography files in `bench/paper` derive from the
[ICLR conference template](https://github.com/ICLR/Master-Template). Their
original attribution headers are retained. The bundled `fancyhdr.sty` retains
its original LaTeX Project Public License notice; the license text is included
in [LICENSES](LICENSES/LPPL-1.3c.txt). `natbib` is supplied by the TeX distribution.
The conference template and third-party style files are not relicensed under
the project's MIT license.

## Model responses

Released JSONL files contain model-generated final responses and evaluation
metadata. Provider and model identifiers accompany the records. Their inclusion
does not grant rights to any model or alter the relevant provider's terms.
Private reasoning text and machine-level collection logs are not part of the release.
