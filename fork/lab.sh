#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
if [[ "${PAPERLESS_TEST_ENGINE:-podman}" == docker ]]; then
	compose=(docker compose)
else
	compose=(podman-compose --in-pod=false)
fi
# Do not inherit a developer's application .env file.
compose+=(--env-file /dev/null -p paperless-fork-lab -f fork/compose.yaml)
case "${1:-}" in
	up) "${compose[@]}" up -d ;;
	stop) "${compose[@]}" stop ;;
	down) "${compose[@]}" down ;;
	logs) "${compose[@]}" logs --tail=80 paperless mock ;;
	status) "${compose[@]}" ps ;;
	smoke) python3 fork/smoke.py ;;
	*) echo "Usage: bash fork/lab.sh {up|stop|down|logs|status|smoke}" >&2; exit 2 ;;
esac
