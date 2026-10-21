# Pinned OpenVINO Model Server 2026.4.1 GPU image. Includes the Intel runtime.
FROM openvino/model_server@sha256:a928903fe429f1e3e27107cc45932d30d95febfd2d1159dc50869c3eac76fc58

USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-numpy && \
    rm -rf /var/lib/apt/lists/*
COPY probe.py /opt/mediaforge/probe.py
USER ovms
