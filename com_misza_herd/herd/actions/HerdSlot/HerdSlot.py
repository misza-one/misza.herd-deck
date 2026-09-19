"""One key = one Omaherd agent. Project is the face; kind is the color."""

from __future__ import annotations

import os
import subprocess
import threading
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib

from src.backend.PluginManager.InputBases import KeyAction

from ...render import breath_step, render_agent, render_empty

ATTACH_HELPERS = [
    os.path.expanduser("~/.config/omarchy/plugins/io.github.salemsayed.omaherd/omaherd-attach"),
]
LOG_PATH = os.path.expanduser("~/.cache/misza-herd-deck.log")
HERDR_OPTIONS_WITH_VALUES = {"--session", "--remote", "--remote-keybindings"}
HERDR_NONCLIENT_FLAGS = {"--no-session", "--default-config", "--skill", "--version", "-V", "--help", "-h"}


def _log(message: str) -> None:
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as output:
            output.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except OSError:
        pass


def _option_value(command: list[str], option: str, default: str = "") -> str:
    for index, part in enumerate(command[1:], start=1):
        if part == option and index + 1 < len(command):
            return command[index + 1]
        if part.startswith(option + "="):
            return part.split("=", 1)[1]
    return default


def _is_herdr_client(command: list[str]) -> bool:
    if not command or os.path.basename(command[0]) != "herdr":
        return False
    if any(flag in HERDR_NONCLIENT_FLAGS for flag in command[1:]):
        return False
    skip_value = False
    for part in command[1:]:
        if skip_value:
            skip_value = False
            continue
        if part in HERDR_OPTIONS_WITH_VALUES:
            skip_value = True
            continue
        if any(part.startswith(option + "=") for option in HERDR_OPTIONS_WITH_VALUES):
            continue
        if part.startswith("-"):
            continue
        return False
    return True


def _is_remote_herdr_client(command: list[str], host: str, session: str) -> bool:
    if not command or os.path.basename(command[0]) != "ssh":
        return False
    try:
        separator = command.index("--")
    except ValueError:
        return False
    if separator + 2 >= len(command) or command[separator + 1] != host:
        return False
    marker = f"exec herdr --session {session}"
    return any(marker in part for part in command[separator + 2:])


def _herdr_client_running(host: str, session: str, proc_root: str = "/proc") -> bool:
    try:
        entries = os.scandir(proc_root)
    except OSError:
        return False
    with entries:
        for entry in entries:
            if not entry.name.isdigit():
                continue
            try:
                with open(os.path.join(entry.path, "cmdline"), "rb") as process:
                    raw = process.read()
            except OSError:
                continue
            command = [part.decode("utf-8", "replace") for part in raw.split(b"\0") if part]
            if host != "local" and _is_remote_herdr_client(command, host, session):
                return True
            if not _is_herdr_client(command):
                continue
            remote = _option_value(command, "--remote")
            if host == "local":
                if remote:
                    continue
            elif remote != host:
                continue
            if _option_value(command, "--session", "default") == session:
                return True
    return False


def _run_control_command(command: list[str]) -> bool:
    try:
        result = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=10,
        )
    except OSError as error:
        _log(f"error {error}")
        return False
    except subprocess.TimeoutExpired:
        _log("focus timeout")
        return False
    output = " ".join(str(result.stdout or "").split())
    suffix = f" output={output[:400]}" if output else ""
    _log(f"focus exit={result.returncode}{suffix}")
    return result.returncode == 0


def _run_and_wait(command: list[str]) -> None:
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as error:
        _log(f"error {error}")
        return
    _log(f"started pid={process.pid}")
    _log(f"exit={process.wait()}")


def _full_client_command(attach: str, host: str, session: str) -> list[str]:
    return [
        "omarchy-launch-terminal",
        attach,
        "--host", host,
        "--session", session,
    ]


def _run_focus_sequence(command: list[str], host: str, session: str) -> None:
    if _herdr_client_running(host, session):
        _run_and_wait(command)
        return
    if _run_control_command([*command, "--no-attach"]):
        _run_and_wait(_full_client_command(command[0], host, session))


class HerdSlotAction(KeyAction):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._client = None
        self._agent = None
        self._last_key = None
        self._timer = 0
        self._attach = next((p for p in ATTACH_HELPERS if os.path.isfile(p)), None)

    def slot(self) -> int:
        try:
            return max(0, min(14, int(self.get_settings().get("slot", 0))))
        except (TypeError, ValueError):
            return 0

    def on_ready(self) -> None:
        self.set_top_label("", update=False)
        self.set_center_label("", update=False)
        self.set_bottom_label("", update=False)
        self._client = self.plugin_base.get_herd_client()
        self._client.subscribe(self)
        self._paint(self._client.snapshot)
        self._client.refresh_now()
        self._ensure_timer()

    def on_update(self) -> None:
        if self._client is not None:
            self._paint(self._client.snapshot)

    def on_tick(self) -> None:
        if self._agent is not None and self._agent.status in ("working", "blocked", "done"):
            self._paint(self._client.snapshot if self._client else None)

    def on_key_down(self, *args, **kwargs) -> None:
        self._focus_agent()

    def on_key_up(self, *args, **kwargs) -> None:
        pass

    def on_key_short_up(self, *args, **kwargs) -> None:
        pass

    def on_key_hold_start(self, *args, **kwargs) -> None:
        pass

    def on_key_hold_stop(self, *args, **kwargs) -> None:
        pass

    def _focus_agent(self) -> None:
        agent = self._agent
        if agent is None or agent.pane_id == "" or self._attach is None:
            _log(f"skip slot={self.slot()} attach={bool(self._attach)}")
            return
        command = [
            self._attach,
            "--host", agent.host,
            "--session", agent.session,
            "--target", agent.pane_id,
            "--workspace", agent.workspace,
            "--hostname", agent.hostname,
            "--timeout", "3",
            "--focus",
        ]
        _log(
            f"focus slot={self.slot()} host={agent.host} session={agent.session} "
            f"workspace={agent.workspace} pane={agent.pane_id} tab={agent.tab_number}"
        )
        threading.Thread(
            target=_run_focus_sequence,
            args=(command, agent.host, agent.session),
            name="MiszaHerdFocus",
            daemon=True,
        ).start()

    def on_herd_snapshot(self, snapshot) -> None:
        GLib.idle_add(self._paint, snapshot)

    def on_removed_from_cache(self) -> None:
        self._stop_timer()
        if self._client is not None:
            self._client.unsubscribe(self)
            self._client = None
        super().on_removed_from_cache()

    def _ensure_timer(self) -> None:
        if self._timer:
            return
        self._timer = GLib.timeout_add(90, self._pulse)

    def _stop_timer(self) -> None:
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0

    def _pulse(self) -> bool:
        agent = self._agent
        if agent is not None and (agent.status in ("working", "blocked", "done") or agent.branch):
            self._paint(self._client.snapshot if self._client else None)
        return True

    def _paint(self, snapshot) -> bool:
        if not self.on_ready_called or self.page is None:
            return False
        agents = list(snapshot.agents) if snapshot is not None else []
        index = self.slot()
        agent = agents[index] if 0 <= index < len(agents) else None
        self._agent = agent
        now = time.monotonic()
        if agent is None:
            key = ("empty",)
            image = render_empty()
        else:
            motion = breath_step(now) if agent.status in ("working", "blocked", "done") else 8
            branch_step = int(now * 4) if agent.branch else 0
            key = (agent.workspace, agent.kind, agent.status, agent.host,
                   agent.pane_id, agent.branch, motion, branch_step)
            image = render_agent(agent.workspace, agent.kind, agent.status, agent.host, now, branch=agent.branch)
        if key == self._last_key:
            return False
        self._last_key = key
        self.set_media(image=image, size=1.0, update=True)
        return False

    def get_config_rows(self):
        row = Adw.SpinRow.new_with_range(0, 14, 1)
        row.set_title("Herd slot")
        row.set_subtitle("0 follows Omaherd order")
        settings = self.get_settings()
        row.set_value(float(self.slot()))
        if "slot" not in settings:
            settings["slot"] = self.slot()
            self.set_settings(settings)
        row.connect("changed", self._on_slot_changed)
        return [row]

    def _on_slot_changed(self, spin):
        settings = self.get_settings()
        settings["slot"] = int(round(spin.get_value()))
        self.set_settings(settings)
        self._last_key = None
        if self._client is not None:
            self._paint(self._client.snapshot)
