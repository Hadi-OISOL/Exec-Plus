#!/usr/bin/env bash
# Use case: Provisions individually revocable SSH keys for eight private-demo users.
# What it does: Restricts the new OS identity to application forwarding without altering other accounts.

set -euo pipefail
umask 077
root=/sdb-disk/OISOL_ExecPLUS
test "$(id -u)" -eq 0
if ! id execplus-demo >/dev/null 2>&1; then
    useradd --system --create-home --home-dir /var/lib/execplus-demo --shell /bin/sh execplus-demo
fi
install -d -m 700 -o execplus-demo -g execplus-demo /var/lib/execplus-demo/.ssh
install -d -m 700 -o administrator -g administrator "$root/secrets/tunnels"
authorized=$(mktemp)
trap 'rm -f "$authorized"' EXIT
for number in {1..8}; do
    key="$root/secrets/tunnels/demo$number"
    if ! test -f "$key"; then
        ssh-keygen -q -t ed25519 -N '' -C "execplus-demo-$number" -f "$key"
        chown administrator:administrator "$key" "$key.pub"
    fi
    printf 'restrict,port-forwarding,permitopen="127.0.0.1:18400",permitopen="127.0.0.1:18401" ' >> "$authorized"
    cat "$key.pub" >> "$authorized"
done
keys=/var/lib/execplus-demo/.ssh/authorized_keys
if test -e "$keys" && ! cmp -s "$authorized" "$keys"; then
    printf 'Existing demo keys differ; review them before replacement.\n' >&2
    exit 1
fi
install -m 600 -o execplus-demo -g execplus-demo "$authorized" "$keys"
config=/etc/ssh/sshd_config.d/90-execplus-demo.conf
if test -e "$config" && ! cmp -s "$root/source/deploy/vps/90-execplus-demo.conf" "$config"; then
    printf 'Existing SSH demo configuration differs; review it before replacement.\n' >&2
    exit 1
fi
install -m 644 "$root/source/deploy/vps/90-execplus-demo.conf" "$config"
if ! /usr/sbin/sshd -t; then
    rm -f "$config"
    exit 1
fi
systemctl reload ssh
printf 'Eight private tunnel keys prepared; distribute one key per demo user securely.\n'
