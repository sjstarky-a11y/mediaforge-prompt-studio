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
- operating system and Docker Desktop/Engine versions;
- clear reproduction steps;
- expected and observed behavior; and
- the minimum logs needed to reproduce the problem, with secrets removed.

The project runs local AI services and exposes them only on `127.0.0.1` by
default. Do not change bindings to `0.0.0.0` unless you understand and accept
the network exposure.

Docker Model Runner's local API is unauthenticated by design. MediaForge binds
its own services to `127.0.0.1` and lists only models reported by the local DMR
instance. Do not expose port `12434`, the image-service port, or the MediaForge
application port to untrusted networks.

Optional and custom models execute under their respective local inference
runtimes. Review model licenses and provenance before installing them.

Linux `doctor.sh --save` does not copy the `.env` file or include prompt and
model-response bodies. It does include selected non-secret runtime settings and
recent service logs, so review the generated report before attaching it to an
issue. MediaForge does not request `sudo` unless the official Docker Model Runner
package must be installed on a supported native Linux system.
