---
sidebar_position: 1
title: Development Documentation
description: Development guides for Paperless NGX contributors
---

# Development Documentation

Welcome to the Paperless NGX development guides. This section covers tools, processes, and configurations used during development.

## Available Guides

### [Codecov Configuration](./codecov-configuration.md)
Manage code coverage tracking across backend and frontend components.

- Component-based coverage tracking (backend/frontend)
- Coverage flags for Python and Node.js versions
- Pull request coverage status checks
- Bundle size analysis for JavaScript
- Threshold configuration and best practices
- Troubleshooting coverage integration issues

## Quick Navigation

### I want to...

**Understand code coverage requirements**
→ Read [Codecov Configuration](./codecov-configuration.md)

**Check why a PR failed coverage checks**
→ See [Troubleshooting](./codecov-configuration.md#troubleshooting) in Codecov Configuration

**Add a new Python version to coverage**
→ Follow [Adding a New Python Version](./codecov-configuration.md#adding-a-new-python-version)

**Adjust coverage thresholds**
→ See [Adjusting Coverage Thresholds](./codecov-configuration.md#adjusting-coverage-thresholds)

## Development Environment

For setting up a development environment:
- Backend: Python with Django and Celery
- Frontend: TypeScript with React and Angular
- See DevContainer Setup in the repository root (.devcontainer/README.md)

## Testing

### Backend Tests

Run Python tests with coverage:

```bash
pytest --cov=src --cov-report=xml
```

Coverage requirements:
- New code: 100% target, 75% minimum
- Overall: 1% minimum change allowed

### Frontend Tests

Run TypeScript/React tests with coverage:

```bash
npm run test:coverage
```

Coverage requirements:
- New code: 100% target, 75% minimum
- Overall: 1% minimum change allowed
- Bundle size: Warn if over 1MB

## Code Review

Pull requests require:
- All tests passing on Python 3.10, 3.11, 3.12
- All tests passing on Node.js 24.x
- Coverage targets met for new code
- No bundle size increase over 50KB
- Maintainer approval

---

**Last Updated**: 2026-01-20

For additional development information, see the Contributing Guide in the repository root.
