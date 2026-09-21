"""StreamController entry point for the Misza Herd plugin."""

from src.backend.PluginManager.ActionHolder import ActionHolder
from src.backend.PluginManager.ActionInputSupport import ActionInputSupport
from src.backend.PluginManager.PluginBase import PluginBase
from src.backend.DeckManagement.InputIdentifier import Input

from .herd.actions.HerdSlot.HerdSlot import HerdSlotAction
from .herd.client import HerdClient


class MiszaHerdPlugin(PluginBase):
    def __init__(self) -> None:
        super().__init__()

        self.herd_client = HerdClient()

        self.herd_slot_holder = ActionHolder(
            plugin_base=self,
            action_core=HerdSlotAction,
            action_id="com_misza_herd::HerdSlot",
            action_name="Herd Slot",
            action_support={
                Input.Key: ActionInputSupport.SUPPORTED,
                Input.Dial: ActionInputSupport.UNSUPPORTED,
                Input.Touchscreen: ActionInputSupport.UNSUPPORTED,
            },
        )
        self.add_action_holder(self.herd_slot_holder)

        self.register(
            plugin_name="Misza Herd",
            github_repo="https://github.com/misza-one/misza.herd-deck",
            plugin_version="0.1.0",
            app_version="1.5.0",
        )

    def get_herd_client(self) -> HerdClient:
        return self.herd_client

    def on_remove(self) -> None:
        self.herd_client.shutdown()
