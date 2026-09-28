# VeilDrop

A Django platform for expiring file links, anonymous support requests, and Telegram-assisted delivery.

## Features

- Upload and expiring-link workflows
- Administrative file and support views
- Telegram bot integrations
- Docker Compose development environment

## Run locally

```bash
cd file_sharing
docker compose -f docker-compose.dev.yml up --build
```

Provide Telegram and Django settings through environment variables before enabling bot services.
