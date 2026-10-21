# Security

## Scope

The current v0.4 preview is under development. Older releases remain available
for reference; continued security maintenance of those versions is not promised.

## Report privately

Use [GitHub private vulnerability reporting](https://github.com/sjstarky-a11y/mediaforge-prompt-studio/security/advisories/new)
if available. Otherwise contact the owner privately using an available contact
method on the [owner's profile](https://github.com/sjstarky-a11y).
Do not post vulnerability details, credentials or private data in a public issue.

Include the version, OS, affected component, minimal reproduction and impact.
Share only the sanitized evidence needed to reproduce the problem.

## Local services and data

App and inference ports bind to localhost by default. Keep Model Runner and these
ports off untrusted networks. Review third-party model licenses and provenance.

Local `.env`, `local/`, model caches and runtime reports are excluded from public
packages. The shareable Doctor report excludes model names, prompts, responses,
paths, URLs and logs. Detailed status output is local and must be reviewed before
sharing. See [troubleshooting](docs/TROUBLESHOOTING.md#share-a-report).
