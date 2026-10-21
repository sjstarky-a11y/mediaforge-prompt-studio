# Troubleshooting

| Symptom | First step |
| --- | --- |
| App does not open | Start Docker; run the launcher with `status` |
| First image is slow / preparing | Allow the initial download and model loading to finish |
| Intel was detected but CPU is selected | Check the driver and GPU bridge; run `doctor` |
| Text uses Model Runner | Intel may be preparing, have insufficient reported memory, or a DMR model was explicitly selected |
| Port is already in use | Stop the other installation or change ports in local `.env` |
| Text or image changes the idea | Review the result manually; report a minimal public example |

## Memory after stopping

Use the launcher **stop** action. Closing the browser alone does not stop services.
To check what remains:

```text
docker ps
docker model ps
```

Intel models unload when their containers stop. Docker Model Runner is a shared
service; if a model is still listed, use `docker model unload <model-name>` only
when no other application needs that model. This keeps downloaded files on disk.

Docker Desktop's **Images** list shows disk storage. An image marked **in use**
can be referenced by a stopped container; this does not prove active GPU/RAM use.

On Windows, `vmmemWSL` can retain allocated RAM and file cache after services stop.
WSL's [automatic memory reclamation](https://learn.microsoft.com/en-us/windows/wsl/wsl-config)
returns unused memory to Windows. Running unrelated containers still needs memory.
[Docker's WSL guidance](https://docs.docker.com/desktop/features/wsl/) explains this behavior.
Do not shut down shared Docker/WSL sessions while another application needs them.

## Share a report

Run the launcher with **doctor**. It saves `runtime/doctor-report.json` inside the
system/source folder. The allowlist excludes model names, prompts, responses,
local paths, URLs and logs.

The **status** action is more detailed and may show local settings. Review its
output before sharing. Never post `.env`, model inventories, private prompts,
full logs, tokens or screenshots containing private information.

[Open a bug report](https://github.com/sjstarky-a11y/mediaforge-prompt-studio/issues/new/choose)
with the version, OS, component, reproduction steps and expected/actual result.
