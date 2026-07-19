# Security Policy

## Supported Versions

Security fixes are provided for the latest released version of `pylibmspack`.
Older releases may receive fixes when the patch is low-risk and the affected API
is still supported.

## Reporting a Vulnerability

Please report vulnerabilities privately through GitHub's private vulnerability
reporting for this repository. If that is unavailable, contact the maintainer
directly rather than opening a public issue with exploit details.

Include:

- affected `pylibmspack` version and platform
- the archive format involved
- a minimal reproducer or sample file, if it can be shared safely
- expected and observed behavior

## Security Model

`pylibmspack` processes archive and compression formats that may come from
untrusted sources. Safe extraction is enabled by default and rejects absolute
paths, drive-letter paths, UNC paths, and `..` traversal after path
normalization. Raw extraction helpers intentionally bypass these checks and
should only be used with trusted inputs.

Read and extraction APIs enforce a caller-configurable `max_size` while
decompressed output is being written. This is intended to reduce decompression
bomb impact and accidental memory or disk use, but callers that process
untrusted inputs should still apply their own file-size, time, and isolation
limits. Prefer explicit, application-specific `max_size` values instead of
relying on the defaults when accepting files from arbitrary users.

CAB and CHM bulk extraction also enforce `max_total_size` and `max_files`
defaults to reduce multi-file archive expansion risk. Safe extraction rejects
symlinked destination directories, symlinked parent directories, and symlinked
output paths before opening output files. For hostile inputs, extract into a
fresh private directory that untrusted users cannot modify during extraction.

Wheels bundle libmspack. The vendored source tarball is SHA-256 verified during
builds, and release CI builds the bundled shared library from that source.

## Fuzzing and Continuous Analysis

Untrusted archive parsing is covered by both Python API fuzzing and native
libFuzzer harnesses for CAB, CHM, SZDD, KWAJ, HLP LZSS, OAB full downloads, and
OAB incremental patches. The Python fuzz smoke covers both in-memory inputs and
disk-backed public APIs. CI runs smoke fuzzing on pull requests and security
jobs, plus a parser exposure check that fails when a supported format is missing
from wrappers, fuzz targets, seed routing, or binding hardening checks.
ClusterFuzzLite is configured for PR fuzzing, scheduled batch fuzzing, and corpus
pruning using the native libFuzzer harnesses. This is an in-repository GitHub CI
setup and does not depend on an external OSS-Fuzz project entry.

For high-risk deployments, run longer local or CI fuzzing campaigns before
shipping parser changes and retain crashing inputs as regression tests. Public
seed corpora and minimized reproducer inputs may appear in crash reports, so do
not add confidential samples to the committed seed corpus.
