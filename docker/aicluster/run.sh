#!/bin/bash
docker \
  run \
  -p 8091:8091 \
  --rm \
  -it \
  -v $(pwd):/aicluster \
  --workdir=/aicluster \
  koash/aicluster:0.1.0 \
  $@
