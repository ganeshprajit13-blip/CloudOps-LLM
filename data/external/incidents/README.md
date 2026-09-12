# danluu/post-mortems — Public Cloud Incident Post-Mortem Collection

## What It Contains

A curated, community-maintained collection of links to real-world publicly
published incident post-mortems from major technology companies. Covers
incidents from 2012 to present (2026).

The repository README contains **hundreds of links** to post-mortems published
by organizations including:
- Amazon Web Services (EC2, DNS, S3, VPC, Route 53)
- Cloudflare (WAF, BGP routing, CDN, R2)
- GitHub (availability, DNS, database)
- Facebook/Meta (networking, configuration)
- CircleCI (database, job distribution)
- Datadog, Google, Twitter, Netflix, Spotify, and many others

Categories: Config Errors, Hardware/Power Failures, Conflicts, Time (clock
skew), Database, Uncategorized.

## Source

- **Repository**: https://github.com/danluu/post-mortems
- **Author**: Dan Luu (danluu) + community contributors
- **GitHub Stars**: 12,304
- **Active Since**: 2015

## License

**No explicit LICENSE file in the repository.**

The compiled list of links is community-contributed and publicly hosted.
Each linked post-mortem is published by its respective company on their
public engineering blogs and is governed by each company's Terms of Service.

Legal basis for use:
- The link collection itself is factual information (URLs + short descriptions)
- Factual information is not copyrightable
- This is broadly accepted research/educational use
- The README links to publicly-accessible URLs

**Training use**: Downloading and training on the text of individual
post-mortems from their original URLs requires evaluation of each company's
Terms of Service. Using the URL index for RAG is generally acceptable for
non-commercial research.

## Downloaded Files

| File | Size | SHA-256 |
|------|------|---------|
| `danluu-post-mortems-master.zip` | 39,456 bytes | `8CF2D68BF6E15FFBBFE3B2A38F1C3D847BF07D13132B3B64D6BD60D1BC3E8D17` |

Downloaded: 2026-09-11

**Note**: The ZIP contains only the README.md and repository metadata — NOT
the full text of post-mortems. The actual post-mortem content resides at
external URLs.

## Data Types

- **Incidents**: Structured references to real incident post-mortems
- Format: Markdown README with categorized links and 1-2 sentence summaries
- Not binary data/time-series

## Cloud/Provider

Multi-cloud and multi-provider:
- AWS (multiple entries)
- GCP
- Cloudflare
- GitHub
- Various SaaS providers

## Services Covered

DNS, BGP routing, WAF, CDN, databases, Kubernetes, EC2, R2, Workers,
CloudFront, PostgreSQL, configuration management, service discovery.

## Why It Is Useful for CloudOps

1. **Real incidents** from production systems — not synthetic
2. **Root cause diversity** — covers config errors, hardware failures, timing issues, DB failures
3. **Modern incidents** — includes incidents up to 2026
4. **CloudOps-relevant patterns** — AWS, networking, infrastructure failures well-represented
5. **Curated quality** — community-vetted, reputable sources only
6. **Incident narrative patterns** — teaches LLMs how real incidents are reported and analyzed

## Known Limitations

- The ZIP only contains the README with links — not the full post-mortem text
- Full content extraction requires fetching each URL (100+ external pages)
- Some external links may be archived/offline (web.archive.org used for many)
- No machine-readable structured format — purely human-readable markdown
- No explicit license — training use requires careful legal assessment

## Suitability for Training

⚠️ **CONDITIONAL** — The downloaded ZIP alone is not directly trainable (only
README). Full-text extraction from each linked URL is required first. After
extraction, each post-mortem's terms of use must be evaluated individually.
AWS post-mortems (aws.amazon.com/message/...) are published by AWS under their
terms. Cloudflare blog posts are under Cloudflare's terms. Recommend using as
reference index rather than raw training data.

## Suitability for RAG

✅ **YES (for index/reference)** — The categorized list is immediately useful
as a retrieval index. Post-mortem summaries (1-2 sentence descriptions in the
README) provide factual, searchable incident references for RAG retrieval.
Full-text RAG would require URL fetching.

## Manifest

See: `data/manifests/danluu-post-mortems.manifest.json`
