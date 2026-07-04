# Self-test for the file bridge — simulates the in-game side with no game running.
#
# Run:  python tests/test_bridge.py    (from the live-link/ directory)
#
# A background thread plays the role of the JIP LN tick: it polls cmd.json and
# writes an id-matched reply.json, the way ln_FNVLink.txt will in Phase 3-4. This
# exercises the async round-trip, atomic writes, partial-read tolerance, id
# matching across a relay "restart", heartbeat freshness, and the event cursor.

import json
import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fnv_link_server.bridge import Bridge  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond):
    results.append((name, cond))
    print(f"  [{PASS if cond else FAIL}] {name}")


class FakeGame:
    """Simulates the in-game tick: process new commands, emit state + events."""

    def __init__(self, bridge_dir, tick=0.05):
        self.dir = bridge_dir
        self.tick = tick
        self._stop = threading.Event()
        self._last_cmd_id = 0
        self._seq = 0
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)

    def _p(self, name):
        return os.path.join(self.dir, name)

    def _write(self, name, obj):
        # The real game's WriteToJSON truncates in place (NOT atomic) — emulate
        # that so the relay's partial-read tolerance is genuinely exercised.
        with open(self._p(name), "w", encoding="utf-8") as f:
            f.write(json.dumps(obj))

    def _run(self):
        while not self._stop.is_set():
            # write a fresh heartbeat/state every tick
            self._write("state.json", {
                "ts": int(time.time()), "pos": {"x": 1.0, "y": 2.0, "z": 3.0},
                "cell": "GoodspringsSource", "health": {"cur": 100, "max": 100},
                "caps": 42,
            })
            # process a new command if present
            try:
                with open(self._p("cmd.json"), "r", encoding="utf-8") as f:
                    cmd = json.loads(f.read())
            except (FileNotFoundError, ValueError):
                cmd = None
            if isinstance(cmd, dict) and cmd.get("id", 0) > self._last_cmd_id:
                self._last_cmd_id = cmd["id"]
                ok = cmd.get("type") != "boom"
                self._write("reply.json", {
                    "id": cmd["id"], "ok": ok,
                    "error": "" if ok else "simulated failure",
                })
                if cmd.get("type") == "console":
                    self._seq += 1
                    self._write("events.json", [
                        {"seq": self._seq, "type": "OnDeath",
                         "actor": "NCRTrooper", "isPlayer": False}
                    ])
            time.sleep(self.tick)


def main():
    tmp = tempfile.mkdtemp(prefix="fnvlink_test_")
    bridge = Bridge(tmp)
    bridge.ensure_dir()
    game = FakeGame(tmp)
    game.start()
    time.sleep(0.15)  # let the first heartbeat land

    # 1) heartbeat / state read
    state = bridge.read_state()
    check("state.json read", state is not None and state.get("cell") == "GoodspringsSource")
    check("heartbeat fresh", bool(state and state.get("_fresh")))
    check("is_connected true while ticking", bridge.is_connected())

    # 2) atomic command write — cmd.json is always valid JSON to the reader
    cid = bridge.send_command("console", {"line": "tgm"})
    with open(os.path.join(tmp, "cmd.json"), encoding="utf-8") as f:
        on_disk = json.load(f)
    check("cmd.json atomic + well-formed", on_disk["id"] == cid and on_disk["type"] == "console")
    check("no leftover .tmp", not os.path.exists(os.path.join(tmp, "cmd.json.tmp")))

    # 3) full round-trip via execute()
    reply = bridge.execute("console", {"line": "player.additem f 100"})
    check("execute round-trip ok", reply.get("ok") is True and not reply.get("timed_out"))

    # 4) id-matched: reply id equals the command id, ids strictly increase
    check("reply id matches", reply.get("id") == cid + 1)

    # 5) failure path surfaces, still id-matched
    rfail = bridge.execute("boom")
    check("failure reply surfaced", rfail.get("ok") is False and not rfail.get("timed_out"))

    # 6) events drain once and don't re-deliver (drained-queue model)
    events = bridge.drain_events()
    check("events delivered", len(events) >= 1 and events[0]["type"] == "OnDeath")
    again = bridge.drain_events()
    check("drain prevents re-delivery", again == [])

    # 6b) dialogue events (captured by subtitle polling: {type,name,text}) drain with the spoken
    # text + speaker intact and a relay-assigned seq.
    bridge._write_text_atomic("events.json", json.dumps(
        [{"type": "dialogue", "name": "Sunny Smiles", "text": "Easy, killer.", "gamehour": 9.0}]))
    dlg = bridge.drain_events()
    check("dialogue event drains with text + speaker",
          len(dlg) == 1 and dlg[0].get("text") == "Easy, killer."
          and dlg[0].get("name") == "Sunny Smiles"
          and isinstance(dlg[0].get("seq"), int) and dlg[0]["seq"] >= 1)

    # 7) id seeding survives a relay restart (new Bridge over same dir)
    bridge2 = Bridge(tmp)
    next_id = bridge2.send_command("noop")
    check("restart seeds id above on-disk", next_id > cid + 1)

    # 7b) execute_script stages exec.txt then round-trips, reply ok reflects success
    rscript = bridge.execute_script("set GameHour to 3", label="settime")
    check("execute_script round-trip ok", rscript.get("ok") is True and not rscript.get("timed_out"))
    # execute_script stages a UNIQUE exec_<id>.txt per command (defeats RunBatchScript's
    # per-filename compile cache), carrying its game-relative path in cmd.json "exec".
    exec_name = "exec_%d.txt" % rscript["id"]
    with open(os.path.join(tmp, exec_name), encoding="utf-8") as f:
        staged = f.read()
    check("exec_<id>.txt staged with script source", staged == "set GameHour to 3")

    # 8) chat drains once and doesn't re-deliver, relabelling seq from the relay counter
    bridge._write_text_atomic("chat.json", json.dumps(
        [{"seq": 1, "text": "hello claude", "gamehour": 14.2},
         {"seq": 2, "text": " ", "gamehour": 14.25},  # whitespace-only — must be dropped
         {"seq": 3, "text": "  where am i?  ", "gamehour": 14.3}]))  # trimmed on delivery
    msgs = bridge.drain_chat()
    check("chat messages delivered, blanks dropped + trimmed",
          [m["text"] for m in msgs] == ["hello claude", "where am i?"])
    check("chat seq relabelled by relay", [m["seq"] for m in msgs] == [1, 2])
    check("chat drain prevents re-delivery", bridge.drain_chat() == [])

    # 8b) seed() lays down the v2 chat display-log files (persistent log + the two batches +
    # the injectable UI fragment) over a fresh dir, and does NOT clobber an existing chatlog.
    seeded = Bridge(tempfile.mkdtemp(prefix="fnvlink_seed_"))
    seeded.seed()
    for fn in ("chatlog.json", "chat_recv.txt", "chatlog_render.txt", "chat_inject.xml"):
        check("seed wrote %s" % fn, os.path.isfile(os.path.join(seeded.dir, fn)))
    with open(os.path.join(seeded.dir, "chatlog.json"), encoding="utf-8") as f:
        check("seeded chatlog.json is an empty array", json.load(f) == [])
    seeded._write_text_atomic("chatlog.json", json.dumps([{"role": "you", "text": "keep me"}]))
    seeded.seed()  # re-seed must preserve an existing (non-empty) chatlog
    with open(os.path.join(seeded.dir, "chatlog.json"), encoding="utf-8") as f:
        check("re-seed preserves existing chatlog", json.load(f) == [{"role": "you", "text": "keep me"}])

    # 9) timeout path when the game stops replying
    game.stop()
    time.sleep(0.2)
    rt = bridge.execute("console", {"line": "x"}, timeout=0.4)
    check("timeout reported as not-connected", rt.get("timed_out") is True and rt.get("ok") is False)
    # state goes stale after the game stops ticking
    time.sleep(0.1)
    check("is_connected false after game stops",
          not Bridge(tmp).is_connected(stale_seconds=0.2))

    passed = sum(1 for _, c in results if c)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
