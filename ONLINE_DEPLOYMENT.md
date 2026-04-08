# ONLINE DEPLOYMENT

## Goal

Deploy the `v2` room server to a public URL so the GitHub Pages `v2` site can create and join rooms without any local server.

## Current Pieces

- static client: [docs/v2.html](/home/xincheng/toy/Chase/docs/v2.html)
- room server: [scripts/engine/v2_online_room_server.py](/home/xincheng/toy/Chase/scripts/engine/v2_online_room_server.py)
- Render blueprint: [render.yaml](/home/xincheng/toy/Chase/render.yaml)
- public web config: [docs/data/v2_online_config.json](/home/xincheng/toy/Chase/docs/data/v2_online_config.json)

## Recommended Host

Use Render Web Services.

The room server is a plain Python HTTP service and already supports:

- `0.0.0.0` binding
- dynamic port via `--port`
- CORS for browser clients

## Render Steps

1. Open Render and create a new Web Service from this GitHub repository.
2. Let Render detect the root directory as the repository root.
3. Use the included [render.yaml](/home/xincheng/toy/Chase/render.yaml), or manually set the start command to:

```bash
bash -lc "python3 scripts/engine/v2_online_room_server.py --host 0.0.0.0 --port ${PORT:-8765}"
```

4. After Render gives you a public URL, copy it.

Render note:

- The repository includes a minimal [requirements.txt](/home/xincheng/toy/Chase/requirements.txt) so Render's default Python build step can succeed even though the room server itself only uses the Python standard library.

## Final Client Switch

After the public room server URL exists, edit:

[docs/data/v2_online_config.json](/home/xincheng/toy/Chase/docs/data/v2_online_config.json)

and change it to:

```json
{
  "server_url": "https://your-room-server.onrender.com"
}
```

Then push again.

At that point, the public `v2` page will stop trying local defaults and will create rooms against the public server by default.

## Temporary Developer Overrides

Before the public config is set, the browser can still override the room server through:

- query parameter: `?server=https://your-server.example.com`
- local storage key: `onichase-v2-room-server-url`

These are intended only for development and staging.
