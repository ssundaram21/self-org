#!/bin/bash
# The benchmarks, into data/benchmarks/.
cd "$(dirname "$0")"
set -e
hf download ssundaram/self-org --repo-type dataset --include "benchmarks/*" --local-dir data
