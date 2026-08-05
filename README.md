<!-- markdownlint-disable MD041 -->
![OQTOPUS logo](./docs/asset/oqtopus-logo.png)

# QDI OQTOPUS

[![CI](https://github.com/snuffkin/qdi-oqtopus/actions/workflows/ci.yaml/badge.svg)](https://github.com/snuffkin/qdi-oqtopus/actions/workflows/ci.yaml)
[![codecov](https://codecov.io/gh/snuffkin/qdi-oqtopus/graph/badge.svg?token=RCXTMMXOMV)](https://codecov.io/gh/snuffkin/qdi-oqtopus)
[![pypi version](https://img.shields.io/pypi/v/qdi-oqtopus.svg)](https://pypi.org/project/qdi-oqtopus/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

## Overview

**QDI OQTOPUS** implements the client-side method surface of QDI (Quantum
Device Interface, v0.1 Conceptual Draft) on top of [OQTOPUS
Cloud](https://github.com/oqtopus-team/oqtopus-client), so that OQTOPUS can
be addressed through QDI's `discover` / `authenticate` / `send` / `monitor`
/ `receive` / `estimate_resources` surface.

This is an experimental adapter, not a finished product: its primary goal is
to find out how far QDI's proposal can be mapped onto a real quantum cloud
platform, and to document precisely where it cannot. See
[`docs/gap-analysis.md`](docs/gap-analysis.md) for every point where the two
diverge, and [`docs/qdi-spec-feedback.md`](docs/qdi-spec-feedback.md) for
open questions this raised about the QDI spec itself.

## Documentation

- [Documentation Home](https://qdi-oqtopus.readthedocs.io/)

## Contact

You can contact us by creating an issue in this repository or by email:

- [oqtopus-team[at]googlegroups.com](mailto:oqtopus-team[at]googlegroups.com)

## License

QDI OQTOPUS is released under the [Apache License 2.0](LICENSE).

## Supporting

Describe supporting organizations, grants, or contributors here.
