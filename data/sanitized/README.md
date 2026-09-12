# Sanitized Telemetry & Incident Data

## Purpose
This directory holds dataset files scrubbed of secrets, AWS access keys, passwords, API tokens, IP addresses, PII, and private internal domain names.

## Sanitization Validation
All files in this directory must pass secret scanning (`scan_for_secrets()`) before advancing to normalization.
