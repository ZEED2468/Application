"""CV engine — one pipeline, one rule registry, artifact-is-truth.

A standalone module (Slice 0 + 1: state-machine skeleton + deterministic spine).
It formalizes the existing, test-locked deterministic floor (ats.score,
format_gate, render.build_tex, assert_truth_bounded) into a recorded state
machine over CvRun / CvRunStep rows. It touches neither the generation pipeline
nor the ATS checker yet — the next slice wires it behind a visible surface.

Design invariants (from the master spec): the artifact is the truth (RENDERED
rules run only on text re-extracted from a compiled PDF); one registry, four
consumption points; grounding by construction (uncited content is invalid before
judgment); missing information is asked for, never invented.
"""
