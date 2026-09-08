"""One key = one Omaherd agent. Project is the face; kind is the color."""

from __future__ import annotations

import os
import subprocess
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib

from src.backend.PluginManager.InputBases import KeyAction

from ...render import breath_step, render_agent, render_empty

ATTACH_HELPERS = [
    os.path.expanduser("~/.config/omarchy/plugins/misza.omaherd/omaherd-attach"),
    os.path.expanduser("~/.config/omarchy/plugins/io.github.salemsayed.omaherd/omaherd-attach"),
]


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
        agent = self._agent
        if agent is None or agent.pane_id == "" or self._attach is None:
            return
        try:
            subprocess.Popen(
                [self._attach, "--host", agent.host, "--session", agent.session,
                 "--target", agent.pane_id, "--workspace", agent.workspace,
                 "--hostname", agent.hostname, "--timeout", "3", "--focus"],
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            pass

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
        if agent is not None and agent.status in ("working", "blocked", "done"):
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
            key = (agent.workspace, agent.kind, agent.status, agent.host,
                   agent.pane_id, breath_step(now) if agent.status in ("working", "blocked", "done") else 8)
            image = render_agent(agent.workspace, agent.kind, agent.status, agent.host, now)
        if key == self._last_key:
            return False
        self._last_key = key
        self.set_media(image=image, size=1.0, update=True)
        return False

    def get_config_rows(self):
        row = Adw.SpinRow.new_with_range(0, 14, 1)
        row.set_title("Herd slot")
        row.set_subtitle("0 is whoever needs you most")
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
