# Retired Gate tests

These tested the per-track noise Gate's TRACK knob, MIXER column, encoder
routes, display and audio. The Gate was retired when the TRANSIENT shaper took
over its TRACK and MIXER controls (see `tests/test_transient_page.py`), and the
Gate's audio now ignores saved thresholds. They are kept for history and are
not run by `run_checks.py`. They import fixtures from `tests/`, so to run one
against an older build, copy it back into `tests/`.
