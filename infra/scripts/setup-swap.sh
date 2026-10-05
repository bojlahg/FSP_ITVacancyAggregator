#!/bin/sh
# Своп-файл на проде (идемпотентно): ./setup-swap.sh [размер_МБ], по умолчанию 2048.
# Запускается через workflow «Server ops» (action=swap) или вручную по SSH — см. docs/deploy.md §5.1.
set -eu
SIZE_MB="${1:-2048}"
SWAPFILE=/swapfile

if swapon --show=NAME --noheadings | grep -qx "$SWAPFILE"; then
  echo "swap $SWAPFILE уже включён"
else
  if [ ! -f "$SWAPFILE" ] || [ "$(stat -c %s "$SWAPFILE")" -ne $((SIZE_MB * 1024 * 1024)) ]; then
    rm -f "$SWAPFILE"
    fallocate -l "${SIZE_MB}M" "$SWAPFILE" || dd if=/dev/zero of="$SWAPFILE" bs=1M count="$SIZE_MB"
    chmod 600 "$SWAPFILE"
    mkswap "$SWAPFILE"
  fi
  swapon "$SWAPFILE"
fi

grep -q "^$SWAPFILE " /etc/fstab || echo "$SWAPFILE none swap sw 0 0" >> /etc/fstab
# Своп — подстраховка от OOM, а не рабочая память: ядро уходит в него только при нехватке RAM
echo "vm.swappiness=10" > /etc/sysctl.d/99-itscout-swap.conf
sysctl -q -p /etc/sysctl.d/99-itscout-swap.conf

echo "CPU: $(nproc)"
swapon --show
free -m
