# AMI Create Delivery Playlist Service

FastAPI microservice for creating delivery playlists in ShotGrid from selected versions.

## Overview

Creates a delivery playlist for selected versions with a configurable name. The default playlist name follows the pattern: `delivery_YYYY-MM-DD_##` where the numeric suffix increments.

## Port

Default port: **8082**

Configure via `AMI_CREATE_DELIVERY_PLAYLIST_PORT` environment variable.

## Environment Variables

Required:
- `AYON_API_KEY` - AYON API key for secret retrieval
- `AYON_SERVER_URL` - AYON server URL
- `SG_URL` - ShotGrid/Flow server URL

Optional:
- `AMI_CREATE_DELIVERY_PLAYLIST_PORT` - Service port (default: 8082)
- `HTTP_PROXY` - HTTP proxy URL
- `LOGLEVEL` - Log level (default: DEBUG)

## Running Locally

```bash
cd ami_create_delivery_playlist

# Install dependencies
uv sync

# Run service
uv run -m ami_create_delivery_playlist
```

## Building Docker Image

```bash
docker build -t ami-create-delivery-playlist:latest -f Dockerfile ..
```

## Testing

```bash
curl -X POST http://localhost:8082/ \
  -F "action=ami_create_delivery_playlist" \
  -F "selected_ids=123,456" \
  -F "project_id=789" \
  -F "user_id=1"
```

## Health Check

```bash
curl http://localhost:8082/health
```

## Architecture

- **handlers.py** - AMI action handler (AMICreateDeliveryPlaylist class)
- **app.py** - FastAPI application and request routing
- **templates/** - Jinja2 HTML templates

Depends on `ami_common` for base classes and utilities.
