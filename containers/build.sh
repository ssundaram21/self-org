#!/bin/bash
# The agent containers, for the runtime selforg/config.py will use: SELFORG_RUNTIME (singularity |
# docker), else singularity if it is installed, else docker.
cd "$(dirname "$0")"
set -e

runtime=${SELFORG_RUNTIME:-$(command -v singularity >/dev/null && echo singularity || echo docker)}
for image in claude_code pi; do
    case $runtime in
        singularity) rm -rf "$image" && singularity build --sandbox "$image" "$image.def" ;;
        docker)      docker build -t "selforg-$image" -f "$image.Dockerfile" . ;;
        *)           echo "SELFORG_RUNTIME=$runtime is not one of singularity, docker" >&2; exit 1 ;;
    esac
done
