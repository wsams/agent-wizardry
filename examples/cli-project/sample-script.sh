#!/bin/sh
# Deploy a sample artifact.
#   --env staging|production   Target environment. Default: staging.
#   --dry-run                  Print the plan and write nothing.
set -eu

ENV="staging"
DRY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --env)
      ENV="${2:?--env needs a value}"
      shift 2
      ;;
    --dry-run)
      DRY=1
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [ "$ENV" != "staging" ] && [ "$ENV" != "production" ]; then
  echo "--env must be staging or production" >&2
  exit 2
fi

if [ "$DRY" -eq 1 ]; then
  echo "dry-run env=$ENV"
  exit 0
fi

echo "deploy env=$ENV"
