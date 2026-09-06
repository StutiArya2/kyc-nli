# 0001 — Record architecture decisions

**Status:** accepted · **Date:** 2026-09-06

## Context

This is a milestone-reviewed research project. Decisions get made between
reviews, get forgotten, and then get re-litigated in the review itself with no
record of why the original call was made.

## Decision

Every decision that would be expensive to reverse, or that a reviewer is likely
to challenge, gets a numbered file in `docs/decisions/`. Format: context,
decision, consequences. Never delete one; supersede it with a new file and mark
the old one superseded.

## Consequences

The decision log is the answer to "why is it built this way", and it is the
first thing a new collaborator (or a coding agent) should read after the README.
