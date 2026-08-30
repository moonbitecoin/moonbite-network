#!/bin/bash
# Give the web dashboard a durable data directory of its own.
#
# /var/lib/moonbite is moonbited's datadir, owned by the moonbite user. The
# previous script assumed it was free, dropped the dashboard's databases into
# it and chowned the whole tree to the dashboard user — which would have left
# the Core daemon unable to read its own blocks on next restart.
#
# Restore that directory, and give the dashboard its own.
set -eu

CORE_DATA=/var/lib/moonbite
DASH_DATA=/var/lib/moonbite-dashboard
DASH_USER=$(systemctl show -p User --value moonbite-dashboard)
DASH_USER=${DASH_USER:-dashboard}
CORE_USER=$(systemctl show -p User --value moonbited)
CORE_USER=${CORE_USER:-moonbite}

echo "step: move the dashboard's databases out of the core datadir"
mkdir -p "$DASH_DATA"
for name in chain.db chain.db-wal chain.db-shm exchange.db forum.db merchants.db \
            wall.db wallet_history.db worldcup.db; do
    if [ -e "$CORE_DATA/$name" ]; then
        mv "$CORE_DATA/$name" "$DASH_DATA/$name"
        echo "  moved $name"
    fi
done

echo "step: restore the core datadir to $CORE_USER"
chown -R "$CORE_USER":"$CORE_USER" "$CORE_DATA"
chmod 750 "$CORE_DATA"
ls -ld "$CORE_DATA"

echo "step: own the dashboard directory as $DASH_USER"
chown -R "$DASH_USER":"$DASH_USER" "$DASH_DATA"
chmod 750 "$DASH_DATA"
ls -ld "$DASH_DATA"

echo "step: repoint the service"
cat > /etc/systemd/system/moonbite-dashboard.service.d/persistence.conf <<EOF
[Service]
# Durable state for the web dashboard. Deliberately NOT /var/lib/moonbite,
# which is moonbited's datadir and owned by a different user.
#
# Outside the deploy tree so a cutover cannot take the databases with it, and
# setting this also switches chain persistence on — without it the node is
# in-memory and the chain restarts at height 0 on every restart.
Environment=MOONBITE_DATA_DIR=$DASH_DATA
ReadWritePaths=$DASH_DATA
EOF

systemctl daemon-reload
systemctl restart moonbite-dashboard
sleep 10

echo "step: verify both services"
echo -n "  moonbited        : "; systemctl is-active moonbited
echo -n "  dashboard        : "; systemctl is-active moonbite-dashboard
echo -n "  /wallet          : "
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8050/wallet --max-time 15
echo "  dashboard data   :"; ls "$DASH_DATA" | sed 's/^/    /'
echo "  core datadir owner:"; stat -c '    %U:%G %n' "$CORE_DATA" "$CORE_DATA/blocks"
