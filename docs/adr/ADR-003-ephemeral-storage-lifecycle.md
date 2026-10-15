# ADR-003: Ephemeral Storage Layout & Lifecycle Retention

## Status
Accepted

## Context
Handling user documents, images, and videos requires strict privacy and data protection compliance. Storing raw user media in relational databases causes table bloat, while leaving unexpired files on disk indefinitely creates privacy hazards and unbounded storage costs.

## Decision
1. Separation of concerns: Relational metadata (job parameters, states, checksums) resides in SQL; binary payloads reside in partitioned object storage folders (`quarantine/`, `inputs/`, `artifacts/`, `temp/`).
2. Random non-guessable UUID keys for all stored objects, hiding original client filenames in object paths.
3. Cryptographic integrity checking: Every stored input and output calculates SHA-256 upon write.
4. Ephemeral retention: Files default to short-lived expiry (24 hours for anonymous sessions).

## Consequences
- Clean privacy model ("Privacy by Default").
- Immune to path traversal and IDOR filename leakage.
- Automatic disk reclamation via scheduled cleanup sweeps.
