# Contributing to Poseidon Labs

Thanks for helping improve Poseidon Labs.

This repository is intended to be useful, inspectable and safe to learn from. Contributions should improve reliability, portability, documentation, testing or defensive usefulness without exposing private systems or enabling unauthorised activity.

## Good contributions

Useful contributions include:

- bug reports with reproducible steps
- portability fixes for different Linux environments
- tests for edge cases or failure modes
- clearer documentation and examples
- defensive feature improvements
- safer error handling and validation
- synthetic test fixtures and sample data
- accessibility or usability improvements
- reasoned suggestions for future labs

## Before opening an issue

A useful suggestion should explain:

1. what behaviour should change,
2. why the change would help,
3. any compatibility, privacy or security implications,
4. an example or reproduction where useful.

Search existing issues first so related work can stay together.

## Pull requests

Keep changes focused. A pull request should explain what changed, why it changed, how it was tested, and any limitations that remain.

When adding or changing code:

- preserve the defensive/educational scope of the project
- add or update tests when practical
- avoid committing generated secrets, credentials or real host data
- use synthetic/redacted example output
- document new dependencies and their licences
- do not copy third-party code or assets unless their licence permits redistribution

## Privacy boundary

Never commit or paste:

- passwords, tokens, API keys or recovery material
- private logs containing identifying information
- real private IP addresses or unnecessary network identifiers
- host-specific firewall or security configurations copied from a real protected system
- personal data that is not required for a lawful public example
- exploit details for a live third-party system

Use synthetic examples instead.

## Security-sensitive reports

Do not publish a working exploit, credential, private-system detail or sensitive vulnerability report in a public issue. Follow [SECURITY.md](SECURITY.md).

## Conduct

Debate the code, evidence and design—not the person. Contributions should be technically reasoned and made in good faith.

## Licence

By contributing original material to this repository, you agree that it may be distributed under the repository's MIT License unless the relevant project states otherwise. Do not contribute material you do not have the right to license.
