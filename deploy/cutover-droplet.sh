#!/bin/bash
# Cut the dashboard over to the staged build, rolling back if it does not serve.
set -u

# Branch to deploy. Defaults to main now that the rebuild is merged.
BRANCH="${1:-main}"
REPO=https://github.com/moonbitecoin/MoonBite-Coin.git

OLD=/opt/moonbite-dashboard-old
CUR=/opt/moonbite-dashboard
NEW=/opt/moonbite-next

fail() { echo "CUTOVER-FAILED: $*"; }

echo "step: stage $BRANCH"
rm -rf "$NEW"
git clone -q --branch "$BRANCH" --single-branch "$REPO" "$NEW" || { fail "clone failed"; exit 1; }
(cd "$NEW" && git log --oneline -1 | sed "s/^/  staged: /")

echo "step: back up current deployment"
BK=/root/backups/moonbite-$(date +%Y%m%d-%H%M%S)
mkdir -p "$BK"
cp -a "$CUR"/*.db "$BK"/ 2>/dev/null || true
(cd "$CUR" && git rev-parse HEAD > "$BK/DEPLOYED_COMMIT.txt" 2>/dev/null) || true
echo "  backup: $BK"

echo "step: stop staged test server"
pkill -f 'bind 127.0.0.1:8051' 2>/dev/null || true
sleep 2

echo "step: stop service"
systemctl stop moonbite-dashboard || { fail "could not stop service"; exit 1; }

echo "step: swap directories"
rm -rf "$OLD"
mv "$CUR" "$OLD" || { fail "could not move current aside"; systemctl start moonbite-dashboard; exit 1; }
mv "$NEW" "$CUR" || { fail "could not move new into place"; mv "$OLD" "$CUR"; systemctl start moonbite-dashboard; exit 1; }

echo "step: databases"
# With MOONBITE_DATA_DIR set, durable state lives outside the deploy tree and
# a cutover cannot touch it - which is the point. The copy below only applies
# to a host still keeping its databases beside the code.
DATA_DIR=$(systemctl show -p Environment --value moonbite-dashboard 2>/dev/null | grep -o "MOONBITE_DATA_DIR=[^ ]*" | cut -d= -f2-)
if [ -n "${DATA_DIR:-}" ]; then
    echo "  held outside the deploy tree in $DATA_DIR - nothing to copy"
else
    cp -a "$OLD"/*.db "$CUR"/ 2>/dev/null || true
    echo "  carried across: $(ls "$CUR"/*.db 2>/dev/null | wc -l) database(s)"
fi

echo "step: rebuild venv at the new path"
# venv scripts hardcode absolute paths, so the directory move breaks them.
rm -rf "$CUR/venv"
python3 -m venv "$CUR/venv" >/dev/null 2>&1
"$CUR/venv/bin/pip" install -q --upgrade pip >/dev/null 2>&1
"$CUR/venv/bin/pip" install -q -r "$CUR/requirements.txt" 2>&1 | tail -2
"$CUR/venv/bin/pip" install -q gunicorn 2>&1 | tail -1

echo "step: import check"
if ! (cd "$CUR" && "$CUR/venv/bin/python" -c 'import web_app') 2>/tmp/import_err; then
    fail "app does not import after move"
    head -5 /tmp/import_err
    rm -rf "$CUR"; mv "$OLD" "$CUR"
    systemctl start moonbite-dashboard
    echo "ROLLED-BACK"
    exit 1
fi
echo "  imports fine"

echo "step: restore ownership"
# The clone runs as root but the service runs as its own user, and sqlite needs
# to write WAL sidecars *into the directory*, not just the .db files. Without
# this every write fails with "attempt to write a readonly database".
SVC_USER=$(systemctl show -p User --value moonbite-dashboard)
SVC_USER=${SVC_USER:-dashboard}
chown -R "$SVC_USER":"$SVC_USER" "$CUR"
echo "  owned by $SVC_USER"

echo "step: start service"
systemctl start moonbite-dashboard
sleep 12

echo "step: verify"
CODE=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8050/wallet --max-time 15)
echo "  local /wallet -> $CODE"
if [ "$CODE" != "200" ]; then
    fail "new build does not serve; rolling back"
    systemctl stop moonbite-dashboard
    rm -rf "$CUR"; mv "$OLD" "$CUR"
    systemctl start moonbite-dashboard
    sleep 8
    echo -n "  after rollback /wallet -> "
    curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8050/wallet --max-time 15
    echo "ROLLED-BACK"
    exit 1
fi

echo "CUTOVER-OK"
cd "$CUR" && git log --oneline -1
