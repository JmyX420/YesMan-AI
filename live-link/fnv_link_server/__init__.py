# fnv_link_server — standalone stdio MCP server for the YesMan AI Live Link.
#
# Optional component of YesMan AI. Re-architecture of the
# SkyLink AI concept by Jarvann (MIT). (c) 2026 JmyX. See LICENSE and NOTICE.md.
#
# Lets Claude read state from and issue commands to a RUNNING Fallout: New Vegas
# game, via a file bridge that an in-game JIP LN Script Runner script polls.
# The toolbox works fully without this; talking to a live game requires it.

from .config import SERVER_NAME, SERVER_VERSION

__all__ = ["SERVER_NAME", "SERVER_VERSION"]
