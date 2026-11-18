#!/bin/bash
# The benchmarks, into data/benchmarks/.
cd "$(dirname "$0")"
set -e
huggingface-cli download ssundaram/self-org --repo-type dataset --include "benchmarks/*" --local-dir data
