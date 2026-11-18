# Docker twin of claude_code.def. Built by containers/build.sh as the image selforg-claude_code.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates nodejs npm \
        && rm -rf /var/lib/apt/lists/*
RUN npm install -g @anthropic-ai/claude-code@2.1.232

ENV PATH="/usr/local/bin:$PATH"
