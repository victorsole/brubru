#!/usr/bin/env python3.12
"""Launch a command as a TRUE daemon, detached from this shell's session.

Why this exists: the Catalan OJ backlog runs were launched with
`nohup ... &` and `disown`, and were still killed twice on 26 Aug the moment
the controlling session went away -- both times with ZERO completed items and
orphaned caffeinate children. nohup only ignores SIGHUP; it does not leave the
process group or session, so a process-group kill still takes the job down.

The standard double-fork + setsid sequence puts the child in a brand new
session with no controlling terminal, so nothing that happens to the parent
shell can reach it. stdio is redirected to the log file, never to the parent's
pipes, so the job cannot die on a broken pipe either.

Usage:
    python3.12 scripts/run_detached.py <logfile> <command> [args...]
Prints the daemon PID so the caller can verify liveness later.
"""
import os
import sys


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: run_detached.py <logfile> <command> [args...]", file=sys.stderr)
        return 2
    log_path, cmd = sys.argv[1], sys.argv[2:]
    os.makedirs(os.path.dirname(os.path.abspath(log_path)) or ".", exist_ok=True)

    # First fork: parent returns to the shell immediately.
    if os.fork() > 0:
        os.wait()          # reap the intermediate child, avoid a zombie
        return 0

    os.setsid()            # new session + process group, no controlling tty

    # Second fork: the grandchild is not a session leader, so it can never
    # reacquire a controlling terminal.
    pid = os.fork()
    if pid > 0:
        print(pid, flush=True)
        os._exit(0)

    fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    devnull = os.open(os.devnull, os.O_RDONLY)
    os.dup2(devnull, 0)
    os.dup2(fd, 1)
    os.dup2(fd, 2)
    os.execvp(cmd[0], cmd)   # replaces this process; never returns


if __name__ == "__main__":
    sys.exit(main())
