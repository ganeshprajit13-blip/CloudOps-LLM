# Dataset Provenance & Audit Manifests

## Purpose
This directory contains JSON metadata manifests tracking the provenance, source URL, organization, license, file sizes, checksums, data types, cloud provider, services, and sanitization status of acquired datasets.

## Manifest Schema
Manifests are validated against `data/manifests/dataset_manifest.schema.json`.

## Business Rule
A dataset manifest CANNOT be marked `"processing_status": "ready"` unless both `provenance` and `license` fields are non-empty strings.
