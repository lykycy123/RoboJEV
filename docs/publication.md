# Publication boundary

The public repository contains implementation, tests, portable task configurations, dependency declarations, blank credential examples, licenses, selected screenshots, compressed demonstration videos, and aggregate/episode-level metrics stripped of deployment details.

The following stay private: real environment files, authentication material, proxy endpoints, cluster hostnames and account paths, raw request/response transcripts, complete run directories, token/cost audits, scheduler logs, downloaded environments, build artifacts, and development archives.

Robot meshes are fetched from a pinned upstream revision and verified against a committed manifest. They are not vendored in Git. Their original license is retained.

Before pushing, `scripts/check_publication.py` checks the actual Git index, rejected path patterns, private deployment strings and file size. It scans text without printing matched secrets. The release process also reviews `git diff --cached`, links and the complete initial history. This automated check is a backstop, not a substitute for reviewing selected files.

GitHub Pages serves only `site/` through its dedicated workflow. No live model API, credentials or raw logs are shipped to browsers. Videos are selected demonstrations; the separate evaluation includes failures and identifies seed coverage. The project makes no claims of novel task decomposition or two-stage model control.
