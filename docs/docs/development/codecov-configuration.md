---
sidebar_position: 3
title: Codecov Configuration
description: Code coverage management with Codecov components and flags
---

# Codecov Configuration

This guide documents the Codecov configuration for Paperless NGX, including component management, coverage thresholds, and bundle analysis.

## Overview

Codecov monitors code coverage across the Paperless NGX project, which consists of:
- **Backend**: Python source code in `src/**`
- **Frontend**: TypeScript/React code in `src-ui/**`

The configuration uses components to organize coverage by codebase section and flags to differentiate coverage across Python and Node.js versions.

## Configuration File

The Codecov configuration is defined in `.codecov.yml` in the repository root. This file controls:
- Coverage status checks on pull requests
- Component-based coverage tracking
- Coverage threshold requirements
- Bundle size analysis for JavaScript

## Components

Components allow tracking coverage separately for different parts of the codebase.

### Backend Component

**Component ID**: `backend`
**Paths**: `src/**`
**Purpose**: Python backend application source code

The backend component tracks coverage for all Python code in the `src` directory, including:
- Django application code
- Celery workers and schedulers
- API endpoints
- Data models and business logic

### Frontend Component

**Component ID**: `frontend`
**Paths**: `src-ui/**`
**Purpose**: TypeScript/React frontend application

The frontend component tracks coverage for all TypeScript and JavaScript code in the `src-ui` directory, including:
- React components
- State management logic
- Utility functions
- API client code

## Coverage Flags

Flags differentiate coverage results across different testing environments and runtime versions.

### Backend Python Versions

Codecov captures coverage from tests running on multiple Python versions:

| Flag | Python Version | Path | Carryforward |
|------|---|---|---|
| `backend-python-3.10` | 3.10 | `src/**` | Yes |
| `backend-python-3.11` | 3.11 | `src/**` | Yes |
| `backend-python-3.12` | 3.12 | `src/**` | Yes |

**Why Multiple Versions?**
- Ensures compatibility across Python 3.10, 3.11, and 3.12
- Identifies version-specific issues early
- Maintains coverage for all supported versions

**Carryforward Setting**:
```yaml
carryforward: true
```
Ensures that if a commit doesn't have coverage from a specific version, Codecov carries forward the previous result for that version. This prevents false coverage drops when a particular Python version doesn't run in a CI build.

### Frontend Node.js Version

| Flag | Node.js Version | Path | Carryforward |
|---|---|---|---|
| `frontend-node-24.x` | 24.x | `src-ui/**` | Yes |

**Why Carryforward Shards?**
Frontend coverage uses a single flag (`frontend-node-24.x`) instead of multiple version flags. The carryforward feature merges coverage from multiple CI shards (parallel test runs) automatically without requiring separate flag definitions per shard.

## Coverage Status Checks

### Project-Level Coverage

Codecov requires minimum coverage percentages for entire components:

#### Backend Project Coverage

```yaml
project:
  backend:
    flags:
      - backend-python-3.10
      - backend-python-3.11
      - backend-python-3.12
    paths:
      - src/**
    threshold: 1%
    removed_code_behavior: adjust_base
```

**Threshold**: `1%`
- Minimum coverage drop allowed (adjusted for removed code)
- Conservative threshold prevents major coverage degradation
- Pull requests failing this check can block merging

**Removed Code Behavior**: `adjust_base`
- When code is removed, the base coverage is adjusted proportionally
- Prevents artificial coverage improvements from code deletion
- Maintains meaningful coverage metrics

#### Frontend Project Coverage

```yaml
project:
  frontend:
    flags:
      - frontend-node-24.x
    paths:
      - src-ui/**
    threshold: 1%
    removed_code_behavior: adjust_base
```

Same threshold and behavior as backend, applied to TypeScript/React code.

### Patch-Level Coverage

Codecov enforces stricter requirements for new code in pull requests:

#### Backend Patch Coverage

```yaml
patch:
  backend:
    flags:
      - backend-python-3.10
      - backend-python-3.11
      - backend-python-3.12
    paths:
      - src/**
    target: 100%
    threshold: 25%
```

**Target**: `100%`
- New code should ideally have complete test coverage
- Encourages writing tests for new functionality

**Threshold**: `25%`
- Allows coverage drops up to 25% on patch-level code
- Prevents overly strict enforcement on small PRs
- Balance between quality and practicality

#### Frontend Patch Coverage

```yaml
patch:
  frontend:
    flags:
      - frontend-node-24.x
    paths:
      - src-ui/**
    target: 100%
    threshold: 25%
```

Same thresholds as backend, applied to new frontend code.

## Pull Request Comments

### Comment Layout

```yaml
comment:
  layout: "header, diff, components, flags, files"
  require_bundle_changes: true
  bundle_change_threshold: "50Kb"
```

**Layout Elements**:
- **header**: Summary statistics (coverage change percentage)
- **diff**: Coverage changes in modified files
- **components**: Separate coverage for each component (backend/frontend)
- **flags**: Coverage by version flag
- **files**: File-level coverage details

**require_bundle_changes**: `true`
- Only comment on PRs if JavaScript bundle size changes by more than threshold
- Prevents unnecessary comments on non-bundle changes

**bundle_change_threshold**: `50Kb`
- Flags bundle size changes of 50KB or larger
- Helps catch unintended size increases

### Comment Example

When a pull request changes code coverage, Codecov posts a comment like:

```
## Coverage Report
- Backend: 92.5% → 93.1% (+0.6%)
- Frontend: 78.2% → 79.1% (+0.9%)

### Component Coverage
- **backend**: 93.1% (target: 100% for patches)
- **frontend**: 79.1% (target: 100% for patches)

### Flags
- backend-python-3.10: 93.1%
- backend-python-3.11: 93.1%
- backend-python-3.12: 93.1%
- frontend-node-24.x: 79.1%

### Files Changed
- src/models.py: 95.2% (+2.1%)
- src-ui/components/App.tsx: 82.5% (+1.3%)
```

## Bundle Analysis

### JavaScript Bundle Size Tracking

```yaml
bundle_analysis:
  warning_threshold: "1MB"
  status: true
```

**warning_threshold**: `1MB`
- Warns if JavaScript bundle exceeds 1 megabyte
- Helps prevent bundle bloat over time
- Encourages code splitting and lazy loading

**status**: `true`
- Includes bundle analysis in Codecov status checks
- Bundle size changes appear in PR comments

### Bundle Configuration Reference

For detailed bundle analysis configuration, see:
- [Codecov JavaScript Bundle Analysis](https://docs.codecov.com/docs/javascript-bundle-analysis)
- Bundle analysis integrates with `@codecov/webpack-plugin` (frontend build)

## CI/CD Integration

### Required Configuration

Codecov requires CI to pass before accepting coverage:

```yaml
codecov:
  require_ci_to_pass: true
```

This ensures:
- Tests must pass on all Python/Node.js versions
- Coverage cannot be uploaded if tests fail
- Prevents breaking changes from inflating coverage metrics

### Uploading Coverage

Coverage is uploaded via GitHub Actions using the Codecov action:

```bash
# In GitHub Actions workflow
- uses: codecov/codecov-action@v3
  with:
    files: ./coverage.xml, ./coverage-frontend.json
    flags: backend-python-3.10, frontend-node-24.x
    fail_ci_if_error: true
```

**Process**:
1. Tests run in CI environment
2. Coverage reports generated (pytest for Python, Jest for JS)
3. Codecov action uploads reports to Codecov
4. Codecov processes and analyzes coverage
5. Status checks appear on pull request

## Maintenance and Updates

### Adding a New Python Version

When supporting a new Python version (e.g., 3.13):

1. **Add flag to `.codecov.yml`**:
```yaml
backend-python-3.13:
  paths:
    - src/**
  carryforward: true
```

2. **Update project coverage**:
```yaml
project:
  backend:
    flags:
      - backend-python-3.10
      - backend-python-3.11
      - backend-python-3.12
      - backend-python-3.13
```

3. **Update patch coverage**:
```yaml
patch:
  backend:
    flags:
      - backend-python-3.10
      - backend-python-3.11
      - backend-python-3.12
      - backend-python-3.13
```

4. **Update CI workflows** to run tests on Python 3.13

### Adjusting Coverage Thresholds

If coverage thresholds are too strict or too loose:

```yaml
project:
  backend:
    threshold: 2%  # Increase from 1% to 2%
```

**Consider**:
- Team's coverage standards
- Nature of changes (refactoring vs. new features)
- Historical coverage metrics
- Project maturity and stability goals

:::warning Threshold Impact
Changing thresholds affects which pull requests pass/fail coverage checks. Increase thresholds carefully to avoid lowering code quality expectations.
:::

## Troubleshooting

### Coverage Not Updating

**Symptoms**: Codecov comment doesn't appear on PR, coverage numbers are outdated

**Diagnosis**:
```bash
# Check if tests ran successfully
gh run list -R <owner>/<repo> --limit 10

# Verify coverage files exist
ls -la coverage.xml coverage-frontend.json

# Check Codecov action logs
gh run view <run-id>
```

**Solutions**:
1. Verify CI workflow generates coverage files
2. Ensure `pytest --cov` and Jest coverage are configured
3. Check that Codecov action has correct file paths
4. Verify repository has Codecov token configured

### False Coverage Drops

**Symptoms**: PR shows coverage decrease when only adding tests

**Cause**: Code removal or threshold sensitivity

**Fix**:
```yaml
# Adjust removed_code_behavior
removed_code_behavior: adjust_base  # Handles removed code properly
```

Or increase threshold slightly:
```yaml
threshold: 2%  # Instead of 1%
```

### Bundle Analysis Not Triggered

**Symptoms**: Bundle analysis comment doesn't appear

**Diagnosis**:
1. Check if `@codecov/webpack-plugin` is installed
2. Verify bundle size actually changed by more than 50Kb threshold
3. Check if `src-ui/**` actually contains changes

**Solution**:
```bash
# Check if bundle changed significantly
npm run build
ls -lh dist/bundle.js
```

### Component Coverage Missing

**Symptoms**: Component section missing from Codecov comment

**Cause**: Component paths don't match changed files

**Fix**:
```yaml
component_management:
  individual_components:
    - component_id: backend
      paths:
        - src/**      # Ensure paths match your code structure
    - component_id: frontend
      paths:
        - src-ui/**   # Update if frontend code location changed
```

## Best Practices

1. **Always aim for new code coverage target of 100%**
   - Write tests alongside features
   - Use test-driven development (TDD)
   - Review uncovered code paths

2. **Monitor coverage trends over time**
   - Check component coverage regularly
   - Identify declining coverage areas
   - Address coverage gaps proactively

3. **Balance strictness with pragmatism**
   - Thresholds prevent degradation but shouldn't be overly restrictive
   - Consider exceptions for legacy code with legitimate coverage gaps
   - Use ignore patterns for unreachable code

4. **Test both happy and error paths**
   - Backend: Test API success and error responses
   - Frontend: Test component rendering and state changes
   - Aim for edge case coverage

5. **Review bundle size changes**
   - Monitor JavaScript bundle growth
   - Use code splitting for large feature areas
   - Lazy load components when appropriate

6. **Keep multiple Python/Node versions in CI**
   - Ensures compatibility across versions
   - Catches version-specific bugs early
   - Prevents breaking changes for users on older versions

## References

- [Codecov Configuration Reference](https://docs.codecov.com/docs/codecovyml-reference)
- [Component Management](https://docs.codecov.com/docs/components)
- [Coverage Flags](https://docs.codecov.com/docs/flags)
- [Commit Status Checks](https://docs.codecov.com/docs/commit-status)
- [JavaScript Bundle Analysis](https://docs.codecov.com/docs/javascript-bundle-analysis)
- [Pull Request Comments](https://docs.codecov.com/docs/pull-request-comments)

---

**Last Updated**: 2026-01-20

For questions about coverage configuration or issues with Codecov integration, refer to the [Codecov documentation](https://docs.codecov.com/) or check GitHub Actions workflow logs for coverage upload details.
