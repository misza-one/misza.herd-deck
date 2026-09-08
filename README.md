# Misza Herd Deck

StreamController plugin that mirrors [Misza Omaherd](https://github.com/misza-one/misza.omaherd)
onto an Elgato Stream Deck. Same agents, same order, same attention states.

Each key is one herd slot: status band on top (`MAIN DONE`, `WAIT`, `RUN`),
project name in the agent-kind color, empty slots stay dark. Press a key to
focus that agent, like Enter in Omaherd.

Requires [StreamController](https://github.com/StreamController/StreamController)
and an enabled `misza.omaherd` widget (it reads `omarchy-shell misza.omaherd status`).

## Install

```sh
./install.sh
```

That copies `com_misza_herd` into
`~/.var/app/com.core447.StreamController/data/plugins/` and restarts
StreamController. Add a page of **Herd Slot** actions (slots 0–14), or copy
the `HERD` page if you already have one.

## Remove

```sh
rm -rf ~/.var/app/com.core447.StreamController/data/plugins/com_misza_herd
```
