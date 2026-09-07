#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
compose=(podman-compose --in-pod=false)
# Do not inherit a developer's application .env file.
compose+=(--env-file /dev/null -p paperless-fork-lab -f fork/compose.yaml)
case "${PAPERLESS_TEST_PROVIDER:-native}" in
	native) ;;
	external) compose+=(-f fork/compose.provider.yaml) ;;
	*) echo "PAPERLESS_TEST_PROVIDER must be native or external" >&2; exit 2 ;;
esac
case "${1:-}" in
	up) "${compose[@]}" up -d ;;
	stop) "${compose[@]}" stop ;;
	down) "${compose[@]}" down ;;
	logs) "${compose[@]}" logs --tail=80 paperless mock ;;
	status) "${compose[@]}" ps ;;
	smoke) python3 fork/smoke.py ;;
	*) echo "Usage: bash fork/lab.sh {up|stop|down|logs|status|smoke}" >&2; exit 2 ;;
esac
