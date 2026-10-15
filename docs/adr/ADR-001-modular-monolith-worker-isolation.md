# ADR-001: Modular Monolith API with Isolated Background Worker Pool

## Status
Accepted

## Context
CompressPro AI combines fast, low-latency API interactions (upload authorization, session management, job polling) with computationally heavy, high-risk media transformations (video transcoding, PDF rendering, decompression). Running hundreds of microservices at launch adds unnecessary operational overhead and network latency, while running heavy media decoding directly on web request threads would cause thread starvation and server crashes.

## Decision
We adopt a **Modular Monolith** for the API control plane and an **Asynchronous Worker Pool** with background threads and processes for media jobs.
- API endpoints are non-blocking and return job status tokens immediately.
- Heavy media operations execute in isolated worker workspaces with strict execution timeouts.

## Consequences
- Fast deployment and simple local testing.
- The web server remains 100% responsive under heavy transcoding loads.
- Workers can be scaled or isolated without breaking API contracts.
