"""Where persistent state lives.

A container's filesystem is thrown away on every redeploy. Anything written
beside the code — the block store, the wall, wallet history — therefore
survives only until the next deploy, which is how the chain kept resetting to
height 0 and the wall kept forgetting its certificates.

The fix is a mounted volume, and the only thing the application needs to know
is where it is. That is this module: one directory, resolved once, that every
durable file hangs off.

Resolution order:

1. ``MOONBITE_DATA_DIR`` — an explicit answer always wins.
2. ``/data`` if it exists — the conventional mount point on Railway and most
   container hosts, so mounting a volume there is the whole configuration.
3. The application directory — the local-development case, where there is no
   volume and files beside the code are exactly what a developer expects.

Per-file environment overrides (``MOONBITE_WALL_DB`` and friends) still take
precedence over all of this, so an existing deployment that sets them keeps
working unchanged.
"""

from __future__ import annotations

import os

_APP_DIR = os.path.dirname(os.path.abspath(__file__))

# The conventional volume mount point. Checked for existence rather than
# assumed: on a host without a volume this directory simply is not there, and
# writing to the container root instead would silently look like it worked.
_CONVENTIONAL_MOUNT = "/data"


def data_dir() -> str:
    """The directory durable files belong in, created if it does not exist."""
    explicit = os.environ.get("MOONBITE_DATA_DIR", "").strip()
    if explicit:
        base = explicit
    elif os.path.isdir(_CONVENTIONAL_MOUNT):
        base = _CONVENTIONAL_MOUNT
    else:
        base = _APP_DIR

    os.makedirs(base, exist_ok=True)
    return base


def is_persistent() -> bool:
    """True when a volume looks configured, rather than the app directory.

    Lets a caller default persistence on in production without turning it on
    for every local run and test, where a chain that survives between runs is
    a surprise rather than a feature.
    """
    if os.environ.get("MOONBITE_DATA_DIR", "").strip():
        return True
    return os.path.isdir(_CONVENTIONAL_MOUNT)


def data_path(filename: str, env_override: str | None = None) -> str:
    """Resolve one durable file, honouring its own environment override first.

    Parent directories are created because a path pointing into a volume
    subdirectory is a perfectly reasonable thing to configure, and sqlite's
    failure when the directory is missing ("unable to open database file")
    says nothing about which file or why.
    """
    if env_override:
        override = os.environ.get(env_override, "").strip()
        if override:
            parent = os.path.dirname(os.path.abspath(override))
            os.makedirs(parent, exist_ok=True)
            return override

    return os.path.join(data_dir(), filename)
