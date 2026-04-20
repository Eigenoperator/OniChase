# ONLINE DEPLOYMENT

## Goal

Deploy the room servers to public URLs so the GitHub Pages clients can create and join rooms without any local server.

## Current Pieces

- static v2 client: [docs/v2.html](/home/xincheng/toy/Chase/docs/v2.html)
- static v3 client: [docs/v3.html](/home/xincheng/toy/Chase/docs/v3.html)
- room server: [scripts/engine/v2_online_room_server.py](/home/xincheng/toy/Chase/scripts/engine/v2_online_room_server.py)
- Render blueprint: [render.yaml](/home/xincheng/toy/Chase/render.yaml)
- v2 public web config: [docs/data/v2_online_config.json](/home/xincheng/toy/Chase/docs/data/v2_online_config.json)
- v3 public web config: [docs/data/v3_online_config.json](/home/xincheng/toy/Chase/docs/data/v3_online_config.json)

## Recommended Host

Use Render Web Services.

The room server is a plain Python HTTP service and already supports:

- `0.0.0.0` binding
- dynamic port via `--port`
- CORS for browser clients

## Render Steps

1. Open Render and create a new Web Service from this GitHub repository.
2. Let Render detect the root directory as the repository root.
3. Use the included [render.yaml](/home/xincheng/toy/Chase/render.yaml). It declares two independent web services:

- `onichase-v2-room-server`, for the public v2 Shinkansen game.
- `onichase-v3-room-server`, for the public v3 Tokyo MapLibre game.

If creating services manually, use these start commands.

For v2:

```bash
bash -lc "python3 scripts/engine/v2_online_room_server.py --dataset shinkansen --host 0.0.0.0 --port ${PORT:-8765}"
```

For v3:

```bash
bash -lc "python3 scripts/engine/v2_online_room_server.py --dataset v3-tokyo --host 0.0.0.0 --port ${PORT:-8765}"
```

4. After Render gives each service a public URL, verify `/health`.

Expected v2 health includes:

```json
{
  "dataset_name": "shinkansen",
  "trip_count": 1139
}
```

Expected v3 health includes:

```json
{
  "dataset_name": "v3-tokyo",
  "trip_count": 39450
}
```

Render note:

- The repository includes a minimal [requirements.txt](/home/xincheng/toy/Chase/requirements.txt) so Render's default Python build step can succeed even though the room server itself only uses the Python standard library.

## Final Client Switch

After the public room server URLs exist, edit:

[docs/data/v2_online_config.json](/home/xincheng/toy/Chase/docs/data/v2_online_config.json)

and change it to:

```json
{
  "server_url": "https://your-room-server.onrender.com"
}
```

Then push again.

For v3, edit:

[docs/data/v3_online_config.json](/home/xincheng/toy/Chase/docs/data/v3_online_config.json)

and change it to the v3 server URL:

```json
{
  "server_url": "https://onichase-v3-room-server.onrender.com",
  "required_dataset": "v3-tokyo",
  "server_start_command": "python3 scripts/engine/v2_online_room_server.py --dataset v3-tokyo --host 0.0.0.0 --port ${PORT:-8765}"
}
```

At that point, the public `v2` and `v3` pages will create rooms against their own dataset-specific public servers by default.

## Temporary Developer Overrides

Before the public config is set, the browser can still override the room server through:

- query parameter: `?server=https://your-server.example.com`
- local storage key for v2: `onichase-v2-room-server-url`
- local storage key for v3: `onichase-v3-room-server-url`

These are intended only for development and staging.
