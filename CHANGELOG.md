# Changelog

## Mortgage 014

- Restructured project documentation into a portfolio-ready narrative with
  quickstart/demo runbooks, architecture framing, and troubleshooting.
- Added release-oriented docs (`CHANGELOG`, `RELEASE`) and screenshot placeholders.

## Mortgage 013

- Added full-stack containerization path for frontend + backend via docker-compose.
- Expanded CI to validate backend quality/tests/golden and frontend production build.

## Mortgage 012

- Introduced a minimal React TypeScript UI to run OCR -> index -> underwrite ->
  trace -> replay interactively.
- Added a typed frontend API client with clean error handling.

## Mortgage 011

- Added one-command deterministic demo and smoke runbook targets.
- Added an end-to-end shell workflow validating replay consistency.

## Mortgage 010

- Added golden-case underwriting regression harness with normalized fixtures.
- Added explicit golden update workflow for intentional contract/output drift updates.

## Mortgage 009

- Added `schema_version: "v1"` underwrite response contract.
- Added optional underwrite result/request persistence plus deterministic replay endpoint.

## Mortgage 008

- Added justifier provider seam (`deterministic` / `stub_llm`) for future extensibility.
- Added optional underwrite graph trace capture and retrieval endpoint.

## Mortgage 007

- Migrated underwriting flow to a deterministic LangGraph orchestration pipeline.
- Preserved API response compatibility while improving node-level structure.

## Mortgage 006

- Added evidence lifecycle endpoints (stats/delete/reindex).
- Added retrieval guardrails and observability metrics for safer justification behavior.

## Mortgage 005

- Added deterministic underwrite endpoint combining policy, risk model, and evidence citations.
- Returned structured justification artifacts suitable for audit and review workflows.

## Mortgage 004

- Added filesystem-backed evidence indexing and retrieval for mortgage cases.
- Standardized citation metadata for downstream justification use.

## Mortgage 003

- Added OCR adapter abstraction with local provenance storage.
- Added traceable document/text artifacts for future RAG and underwriting rationale.

## Mortgage 002

- Added JSON-first document intake/extraction pipeline for mortgage feature derivation.
- Added direct document-driven decision endpoint for early integration workflows.

## Mortgage 001

- Implemented deterministic mortgage policy engine with explainable reason codes.
- Added transparent derived metrics (`dti`, `ltv`) in decision responses.
