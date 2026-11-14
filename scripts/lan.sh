#!/usr/bin/env bash
# Make development servers reachable from other devices on the same network.
#
#   bash scripts/lan.sh open  <port>...    print the address to share; on WSL2 also forward the ports
#   bash scripts/lan.sh close <port>...    undo what "open" did
#   bash scripts/lan.sh --dry-run open 5173    show what would run, change nothing
#
# The server itself must listen on 0.0.0.0 (the dev commands in the docs do).
# Outside WSL2 nothing needs forwarding: this only prints the address.
# On WSL2 with default (NAT) networking, other devices cannot reach the virtual machine, so each port
# is forwarded from Windows with a port proxy plus a firewall rule that allows only the local subnet,
# for the network profile currently in use. Windows shows an administrator prompt (UAC) for the user to
# approve; nothing else about the system is changed. "close" removes both again.
set -euo pipefail

dry_run=0
if [ "${1:-}" = "--dry-run" ]; then dry_run=1; shift; fi
action="${1:-}"; shift || true
ports=("$@")

if [ "$action" != open ] && [ "$action" != close ] || [ "${#ports[@]}" -eq 0 ]; then
  sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'
  exit 64
fi
for port in "${ports[@]}"; do
  case "$port" in
    '' | *[!0-9]*) echo "not a port number: $port" >&2; exit 64 ;;
  esac
  if [ "$port" -lt 1024 ] || [ "$port" -gt 65535 ]; then echo "port must be 1024-65535: $port" >&2; exit 64; fi
done

is_wsl() { grep -qi microsoft /proc/version 2>/dev/null; }
ps() { powershell.exe -NoProfile -Command "$1" | tr -d '\r'; }

if ! is_wsl; then
  address="$(hostname -I 2>/dev/null | awk '{print $1}')"
  for port in "${ports[@]}"; do echo "http://${address:-<this machine>}:$port"; done
  echo "(not WSL2: nothing to forward; the server must listen on 0.0.0.0 and the firewall must allow the port)"
  exit 0
fi

wsl_address="$(hostname -I | awk '{print $1}')"
lan_address="$(ps '(Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -ne $null } | Select-Object -First 1).IPv4Address.IPAddress')"
profile="$(ps '(Get-NetConnectionProfile | Where-Object { $_.IPv4Connectivity -eq "Internet" } | Select-Object -First 1).NetworkCategory')"
[ -n "$lan_address" ] || { echo "could not find the Windows LAN address" >&2; exit 1; }
profile="${profile:-Private}"

script='$ErrorActionPreference = "Stop"'$'\n'
for port in "${ports[@]}"; do
  script+="netsh interface portproxy delete v4tov4 listenaddress=$lan_address listenport=$port | Out-Null"$'\n'
  script+="Remove-NetFirewallRule -DisplayName 'dev-lan-$port' -ErrorAction SilentlyContinue"$'\n'
  if [ "$action" = open ]; then
    script+="netsh interface portproxy add v4tov4 listenaddress=$lan_address listenport=$port connectaddress=$wsl_address connectport=$port | Out-Null"$'\n'
    script+="New-NetFirewallRule -DisplayName 'dev-lan-$port' -Direction Inbound -Action Allow -Protocol TCP -LocalPort $port -Profile $profile -RemoteAddress LocalSubnet | Out-Null"$'\n'
  fi
done

if [ "$dry_run" = 1 ]; then
  echo "WSL address: $wsl_address | Windows LAN address: $lan_address | network profile: $profile"
  echo "--- would run elevated in Windows PowerShell:"; printf '%s' "$script"
  exit 0
fi

win_temp="$(wslpath "$(ps '$env:TEMP')")"
file="$win_temp/dev-lan-$$.ps1"
printf '%s' "$script" >"$file"
trap 'rm -f "$file"' EXIT
win_file="$(wslpath -w "$file")"
powershell.exe -NoProfile -Command "Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','$win_file'"

if [ "$action" = open ]; then
  [ "$profile" = Public ] && echo "note: this network is set to 'Public' in Windows; the rule applies to it but only for the local subnet. Switch it to 'Private' if you trust this network."
  for port in "${ports[@]}"; do
    echo "http://$lan_address:$port"
    curl -s -o /dev/null -m 3 "http://$lan_address:$port/" && echo "  reachable through the forward" || echo "  forwarded; start the server on 0.0.0.0:$port if it is not running yet"
  done
else
  echo "closed: ${ports[*]}"
fi
