# Development Setup

This guide explains how to set up the application for development with live reloading for frontend changes.

## Frontend Development with Hot Reloading

The Docker Compose configuration has been set up to support frontend development with hot reloading. This allows you to make changes to the frontend code and see them immediately without having to rebuild the Docker image.

### Getting Started

1. Start the full stack with the development configuration:

```bash
docker-compose up -d
```

2. The frontend development server will be available at http://localhost:4200

3. The main application will be available at http://localhost:8000, but will load the frontend from the development server.

### Making Changes

Any changes you make to files in the `src-ui` directory will be automatically detected by the Angular development server, and the browser will reload to reflect your changes.

### Technical Implementation

The development setup includes:

- A dedicated Node.js container running the Angular development server
- Volume mounts for the `src` and `src-ui` directories
- An environment variable to configure Django to use the external development server
- Disabling the whitenoise middleware to prevent static file errors
- Enabling Django's debug mode to allow CORS requests from the development server

### Troubleshooting

If you encounter errors related to static files like:

```
FileNotFoundError: [Errno 2] No such file or directory: '/usr/src/paperless/static/frontend/ko-KR/favicon.ico'
```

Make sure the `PAPERLESS_DISABLE_WHITENOISE` environment variable is set to `1` in your docker-compose.override.yml file.

If you encounter CORS errors in the browser console like:

```
Access to XMLHttpRequest at 'http://localhost:8000/api/...' from origin 'http://localhost:4200' has been blocked by CORS policy
```

Make sure the `PAPERLESS_DEBUG` environment variable is set to `yes` in your docker-compose.override.yml file. This enables Django's debug mode, which allows CORS requests from the frontend development server.

### Notes

- The `docker-compose.override.yml` file contains the development-specific configuration. If you want to run in production mode, you can use:

```bash
docker-compose -f docker-compose.yml up -d
```

- For backend changes, you may need to restart the webserver service:

```bash
docker-compose restart webserver
```
