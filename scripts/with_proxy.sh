#!/usr/bin/env bash
# Optional per-job bridge to an existing HTTP proxy on the login node.
set -euo pipefail
if [[ -z "${JEV_PROXY_REMOTE_PORT:-}" ]]; then
    exec "$@"
fi
if [[ ! "$JEV_PROXY_REMOTE_PORT" =~ ^[0-9]+$ ]] || (( JEV_PROXY_REMOTE_PORT < 1024 || JEV_PROXY_REMOTE_PORT > 65535 )); then
    echo 'JEV_PROXY_REMOTE_PORT must be a port in 1024..65535' >&2
    exit 2
fi
proxy_local_port=$(python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')
proxy_log=$(mktemp)
proxy_pid=''
child_pid=''
cleanup() {
    if [[ -n "$child_pid" ]]; then kill "$child_pid" 2>/dev/null || true; fi
    if [[ -n "$proxy_pid" ]]; then
        kill "$proxy_pid" 2>/dev/null || true
        wait "$proxy_pid" 2>/dev/null || true
    fi
    rm -f -- "$proxy_log"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP
proxy_ssh_options=()
if [[ -n "${JEV_PROXY_HOST_KEY_ALIAS:-}" ]]; then
    proxy_ssh_options+=(-o "HostKeyAlias=$JEV_PROXY_HOST_KEY_ALIAS")
fi
ssh -F /dev/null -o BatchMode=yes -o ExitOnForwardFailure=yes -o ConnectTimeout=10 -o ServerAliveInterval=15 \
    "${proxy_ssh_options[@]}" \
    -o ServerAliveCountMax=2 -N -L "127.0.0.1:${proxy_local_port}:127.0.0.1:${JEV_PROXY_REMOTE_PORT}" \
    "${JEV_PROXY_HOST:?Set JEV_PROXY_HOST to your SSH login host}" >"$proxy_log" 2>&1 &
proxy_pid=$!
ready=0
for _ in {1..50}; do
    if ! kill -0 "$proxy_pid" 2>/dev/null; then cat "$proxy_log" >&2; exit 1; fi
    if python -c 'import socket,sys; socket.create_connection(("127.0.0.1", int(sys.argv[1])), timeout=.2).close()' "$proxy_local_port" 2>/dev/null; then
        ready=1
        break
    fi
    sleep .2
done
if [[ "$ready" != 1 ]]; then cat "$proxy_log" >&2; exit 1; fi
export http_proxy="http://127.0.0.1:$proxy_local_port" https_proxy="http://127.0.0.1:$proxy_local_port"
export HTTP_PROXY="$http_proxy" HTTPS_PROXY="$https_proxy" all_proxy="$http_proxy" ALL_PROXY="$http_proxy"
"$@" &
child_pid=$!
wait "$child_pid"
child_pid=''
