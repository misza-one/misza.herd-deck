# Misza Herd Deck

StreamController plugin that mirrors [Omaherd](https://github.com/salemsayed/omaherd)
onto an Elgato Stream Deck. Same agents, same attention states, stable slot order.

Each key is one herd slot: status band on top (`MAIN DONE`, `WAIT`, `RUN`),
project name in the agent-kind color, empty slots stay dark. Slots keep a fixed
identity order (the bar re-sorts attention first; the deck does not, so keys
stop jumping), and brief `done`/`blocked` blips between an agent's own steps
need a repeated poll before a key turns yellow/red. Press a key to
focus that agent in an existing HerdR client, or open a full client on its pane.

Requires [StreamController](https://github.com/StreamController/StreamController)
and the Omaherd bar widget (`io.github.salemsayed.omaherd`). The deck reads
`omarchy-shell io.github.salemsayed.omaherd status`.

```bash
omarchy plugin add https://github.com/salemsayed/omaherd.git --enable
```

## Install

```sh
./install.sh
```

That copies `com_misza_herd` into
`~/.var/app/com.core447.StreamController/data/plugins/` and restarts
StreamController. It does **not** write pages or overwrite other plugins.

To put the herd on the deck, copy `pages/HERD.json` into
`~/.var/app/com.core447.StreamController/data/pages/` only if that file
does not already exist, then switch the device to page `HERD` in StreamController
(or `streamcontroller --change-page SERIAL HERD`).

## Agent setup

Paste this to an agent on a machine that already has Omarchy:

```
Set up Misza Herd Deck on this Linux machine (Omarchy + StreamController).

Sources:
- Deck plugin: https://github.com/misza-one/misza.herd-deck.git
- Bar source of truth: Omaherd https://github.com/salemsayed/omaherd.git
  (plugin id io.github.salemsayed.omaherd)

Safety (do not skip):
- Never overwrite or delete existing StreamController pages, settings, or other plugins.
- Never rsync --delete on the parent plugins/ or pages/ directories.
- Only write into:
  ~/.var/app/com.core447.StreamController/data/plugins/com_misza_herd/
- Pages live in:
  ~/.var/app/com.core447.StreamController/data/pages/
- If StreamController is already running, copy files first; restart the app only after asking.
- Only one process may own the USB deck. Do not start a second Stream Deck daemon.
- Do not modify Page 1.json or any page the user already has, except adding a NEW page file if missing.

Install:
1. Ensure StreamController is installed and the user can access the deck (udev).
2. Ensure Omaherd is enabled in Omarchy:
   omarchy plugin add https://github.com/salemsayed/omaherd.git --enable
   (skip add if io.github.salemsayed.omaherd is already enabled)
3. Clone or pull misza.herd-deck. rsync com_misza_herd/ into the plugin path above
   (exclude __pycache__). Updating an existing com_misza_herd folder is OK.
4. Restart StreamController only with consent (or tell the user to restart it).

Configure the deck (after the plugin is loaded):
5. If pages/HERD.json does not exist in the StreamController data dir, copy
   pages/HERD.json from this repo. Do not replace it if it already exists.
6. List devices: streamcontroller --list-devices
   Switch this deck to the new page without touching other pages:
   streamcontroller --change-page SERIAL_NUMBER HERD
   Only do this if the user wants the herd on the hardware now. If they already
   use another page, leave the active page alone and tell them HERD is in the page list.
7. Verify Omaherd IPC: `omarchy-shell io.github.salemsayed.omaherd status`.
   Keys should show the same agents (blocked/done/working/idle). Empty slots stay dark.
   Slots keep a stable order (unlike the bar's attention-first sort), and yellow/red
   appear ~4 s after the state holds (single-poll blips are ignored).
   A key press focuses the agent in an existing HerdR client, or opens a full client on its pane.

Do not fork Omaherd. The deck only consumes its status IPC.
```

## Remove

```sh
rm -rf ~/.var/app/com.core447.StreamController/data/plugins/com_misza_herd
```
