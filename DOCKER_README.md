# Docker Setup for Hyun AI Music Video Generator

This document explains how to set up and run the Hyun AI Music Video Generator using Docker.

## Overview

The application is containerized using Docker and Docker Compose, which provides several advantages:

1. **Consistent Environment**: The application runs in the same environment regardless of the host system.
2. **Easy Deployment**: Simple commands to build and run the application.
3. **Isolated Dependencies**: All dependencies are contained within the Docker image.
4. **Samba Integration**: The Samba share is mounted directly in the container.

## Prerequisites

- Docker Engine (version 20.10.0 or higher)
- Docker Compose (version 2.0.0 or higher)
- Access to the Samba share at `\\hyun.club\videos`

## Configuration

1. **Environment Variables**: Copy `.env.example` to `.env` and fill in the required values:

```bash
cp .env.example .env
```

Make sure to set the following variables:
- `VIDEO_SERVER`: The IP address of the Samba server (default: 172.236.12.109)
- `VIDEO_SERVER_USER`: The username for the Samba share (default: videouser)
- `VIDEO_SERVER_PASSWORD`: The password for the Samba share

2. **Docker Compose Configuration**: The `docker-compose.yml` file defines two services:
   - `app`: The main application container
   - `nginx`: A web server to serve videos over HTTP

## Building and Running

### Build the Docker Image

```bash
docker-compose build
```

### Start the Services

```bash
docker-compose up -d
```

This will start both the application and Nginx containers in detached mode.

### View Logs

```bash
docker-compose logs -f
```

### Stop the Services

```bash
docker-compose down
```

## Accessing the Application

- **Application Logs**: `docker-compose logs -f app`
- **Videos via HTTP**: `http://localhost:8080/videos/filename.mp4`
- **Videos via Samba**: `\\hyun.club\videos\filename.mp4`

## Testing the Upload

You can test the upload functionality using the provided test script:

```bash
# From the host machine
python test_local_upload.py --video path/to/video.mp4 --title "Test Video"

# From inside the container
docker-compose exec app python test_local_upload.py --video /app/data/final_videos/your_video.mp4 --title "Test Video"
```

## Troubleshooting

### Samba Mount Issues

If the Samba share fails to mount, check:

1. **Credentials**: Make sure the username and password are correct in the `.env` file.
2. **Network Access**: Ensure the Docker host can access the Samba server.
3. **Samba Version**: Try changing the `vers=3.0` parameter in `docker-compose.yml` to `vers=2.0` or `vers=1.0`.

### Permission Issues

If you encounter permission issues when writing to the Samba share:

1. **UID/GID**: Adjust the `uid=1000,gid=1000` parameters in `docker-compose.yml` to match the user/group IDs on the Samba server.
2. **Share Permissions**: Make sure the Samba share has write permissions for the specified user.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│  Hyun App       │     │  Nginx          │     │  Samba Server   │
│  Container      │     │  Container      │     │  (hyun.club)    │
│                 │     │                 │     │                 │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         │                       │                       │
         │                       │                       │
┌────────┴───────────────────────┴───────────────────────┴────────┐
│                                                                 │
│                      Docker Network                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

The Hyun App container generates videos and uploads them to the Samba share, which is mounted as a volume in both the app container and the Nginx container. The Nginx container serves the videos over HTTP.

## Security Considerations

- **Credentials**: The Samba credentials are stored in the `.env` file, which should be kept secure and not committed to version control.
- **Network Access**: The Nginx container exposes port 8080, which should be protected by a firewall if deployed in a production environment.
- **Volume Permissions**: The Samba share is mounted with specific user/group IDs, which should be set to restrict access appropriately.
