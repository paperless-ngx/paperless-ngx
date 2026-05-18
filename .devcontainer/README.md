# Paperless-ngx Development Environment

## Overview

Welcome to the Paperless-ngx development environment! This setup uses VSCode DevContainers to provide a consistent and seamless development experience.

### What are DevContainers?

DevContainers are a feature in VSCode that allows you to develop within a Docker container. This ensures that your development environment is consistent across different machines and setups. By defining a containerized environment, you can eliminate the "works on my machine" problem.

### Advantages of DevContainers

- **Consistency**: Same environment for all developers.
- **Isolation**: Separate development environment from your local machine.
- **Reproducibility**: Easily recreate the environment on any machine.
- **Pre-configured Tools**: Include all necessary tools and dependencies in the container.

## DevContainer Setup

The DevContainer configuration provides up all the necessary services for Paperless-ngx, including:

- Redis
- Gotenberg
- Tika

Data is stored using Docker volumes to ensure persistence across container restarts.

## Configuration Files

The setup includes debugging configurations (`launch.json`) and tasks (`tasks.json`) to help you manage and debug various parts of the project:

- **Backend Debugging:**
  - `manage.py runserver`
  - `manage.py document-consumer`
  - `celery`
- **Maintenance Tasks:**
  - Create superuser
  - Run migrations
  - Recreate virtual environment (`.venv` with `uv`)
  - Compile frontend assets

## Getting Started

### Step 1: Running the DevContainer

To start the DevContainer:

1. Open VSCode.
2. Open the project folder.
3. Open the command palette and choose `Dev Containers: Rebuild and Reopen in Container`.

VSCode will build and start the DevContainer environment.

### Step 2: Initial Setup

Once the DevContainer is up and running, run the `Project Setup: Run all Init Tasks` task to initialize the project.

Alternatively, the Project Setup can be done with individual tasks:

1. **Compile Frontend Assets**: `Maintenance: Compile frontend for production`.
2. **Run Database Migrations**: `Maintenance: manage.py migrate`.
3. **Create Superuser**: `Maintenance: manage.py createsuperuser`.

### Debugging and Running Services

You can start and debug backend services either as debugging sessions via `launch.json` or as tasks.

#### Using `launch.json`

1. Press `F5` or go to the **Run and Debug** view in VSCode.
2. Select the desired configuration:
   - `Runserver`
   - `Document Consumer`
   - `Celery`

#### Using Tasks

1. Open the command palette and select `Tasks: Run Task`.
2. Choose the desired task:
   - `Runserver`
   - `Document Consumer`
   - `Celery`

### Additional Maintenance Tasks

Additional tasks are available for common maintenance operations:

- **Recreate .venv**: For setting up the virtual environment using `uv`.
- **Migrate Database**: To apply database migrations.
- **Create Superuser**: To create an admin user for the application.

## Committing from the Host Machine

The DevContainer automatically installs Git pre-commit hooks during setup. However, these hooks are configured for use inside the container.

If you want to commit changes from your host machine (outside the DevContainer), you need to set up prek on your host. This installs it as a standalone tool.

```bash
uv tool install prek && prek install
```

After this, you can commit either from inside the DevContainer or from your host machine.

## Let's Get Started!

Follow the steps above to get your development environment up and running. Happy coding!
