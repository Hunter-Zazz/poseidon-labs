# Poseidon Labs

**Open-source defensive security, Linux, Python, investigation and web-development labs from Project Poseidon.**

> HACK THE PLANET — together.

`poseidon-labs` is the public proof-of-work repository for Hunter + Zazz. The goal is simple: useful work should be inspectable, testable, reusable and improvable rather than accepted on trust.

## What belongs here

This repository publishes sanitised, reusable projects with enough evidence for another person to understand what they do and, where practical, run or test them.

Projects may include:

- defensive Linux and Python utilities
- file-integrity and local system-analysis tools
- safe network and configuration inspection
- log-analysis and reporting utilities
- lawful OSINT, financial-crime and crypto-investigation labs using public or synthetic data
- web-development case studies and reusable components where publication rights permit

Private workstation hardening, credentials, host-specific security controls, operational logs, real network identifiers and sensitive account information do **not** belong here.

## Evidence standard

A substantial project should aim to provide:

1. clear purpose and scope
2. inspectable source code
3. installation and usage instructions
4. automated tests where appropriate
5. synthetic or non-sensitive example output
6. limitations and assumptions
7. security and privacy notes
8. meaningful Git history

The standard is: **do not trust the claim; inspect the work.**

## Project status

| Project | Status | Purpose |
| --- | --- | --- |
| `system-collector/` | VERIFIED BY ARTEFACT | Read-only Linux system information collection and reporting |
| `file-integrity-checker/` | Publication review | SHA-256 local integrity baselining and change detection |
| `network-snapshot/` | In development | Read-only local network configuration snapshot |
| `log-analysis/` | Planned | Parse and summarise selected Linux/security logs using safe sample data |
| `free-firewall-setup/` | Planned | Generic defensive Linux firewall guidance and starter tooling |
| `mac-scrambler/` | Planned | Privacy-oriented MAC randomisation helper and documentation |
| `safe-port-inventory/` | Planned | Local service/port inventory for owned or authorised systems |
| `config-checker/` | Planned | Non-destructive defensive configuration checks |
| `report-generator/` | Planned | Combine safe local-tool outputs into readable reports |
| `financial-crime-labs/` | Planned | Synthetic financial-investigation exercises |
| `crypto-investigation-labs/` | Planned | Public-chain investigation exercises using public/synthetic data |
| `osint-labs/` | Planned | Lawful public-source research and verification workflows |
| `web-projects/` | Active evidence | Web-development case studies and permitted reusable components |

Directories are added when there is real code, documentation or a reproducible lab to publish. Empty portfolio theatre is not useful evidence.

## Contributions and suggestions

Suggestions, bug reports, portability fixes, documentation improvements and code contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

Do **not** post credentials, private logs, personal data, real private network information or exploitable details about a live third-party system in a public issue. See [SECURITY.md](SECURITY.md) for security-reporting guidance.

## Scope and ethics

The repository is designed for defensive engineering, education, investigation using lawful/public/synthetic data, and security work on systems that are owned or explicitly authorised.

**Capability does not equal permission.**

**Protect · Understand · Document · Verify · Report.**

## Licence

Original Project Poseidon code in this repository is released under the [MIT License](LICENSE), unless a project states otherwise. Third-party material retains its original licence and must be reviewed before publication.
