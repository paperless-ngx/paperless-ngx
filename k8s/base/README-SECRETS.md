# Kubernetes Secrets Setup

## IMPORTANT: Secret Management

The `secret.yaml` file contains sensitive credentials and is **NOT** tracked in version control for security reasons.

## Setup Instructions

1. Copy the example template:
   ```bash
   cp secret.yaml.example secret.yaml
   ```

2. Edit `secret.yaml` and replace the placeholder values with secure credentials:
   - `PAPERLESS_DBPASS`: Database password (use a strong random password)
   - `PAPERLESS_SECRET_KEY`: Django secret key (minimum 50 characters)

3. Generate secure random values:
   ```bash
   # Generate database password
   openssl rand -base64 32
   
   # Generate secret key
   openssl rand -base64 64
   ```

## Security Notes

- **NEVER** commit `secret.yaml` to version control
- Use different secrets for each environment (dev/staging/production)
- For production, consider using external secret management:
  - Sealed Secrets
  - External Secrets Operator
  - HashiCorp Vault
  - Cloud provider secret managers (AWS Secrets Manager, GCP Secret Manager, Azure Key Vault)

## File Status

- ✅ `secret.yaml.example` - Template file (tracked in git)
- ❌ `secret.yaml` - Actual secrets (NOT tracked, in .gitignore)
