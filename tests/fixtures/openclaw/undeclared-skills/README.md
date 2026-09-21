# Stealth Browser

Anti-detection browser automation for AI agents. The package ships as a native
OpenClaw plugin and also carries portable Agent Skills under `skills/`.

## Install

Add the plugin to your OpenClaw gateway:

```bash
openclaw plugins install @example/stealth-browser
```

The bundled skills work with any Agent Skills host:

```bash
npx skills add example/stealth-browser
```

## Skills

- `browser-session` — open, drive and close a stealth browser session.

## Configuration

Set `url` to point at an existing browser server, or leave it unset and set
`port` to have the plugin start one locally.
