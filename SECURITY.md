# Security policy

## Supported version

Security fixes currently target the latest public-test release only.

| Version | Supported |
| --- | --- |
| develop / 0.2-dev | Development testing only |
| 0.1a | Yes |
| Earlier public tests | No |

## Reporting a vulnerability

Do not publish credentials, private prompts, personal data, exploit details, or
other sensitive information in a public issue.

Report a suspected vulnerability privately through the repository owner's
GitHub profile. Include:

- affected version;
- Windows and Docker Desktop versions;
- clear reproduction steps;
- expected and observed behavior; and
- the minimum logs needed to reproduce the problem, with secrets removed.

The project runs local AI services and exposes them only on `127.0.0.1` by
default. Do not change bindings to `0.0.0.0` unless you understand and accept
the network exposure.
