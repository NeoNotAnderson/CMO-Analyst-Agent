# Security Policy

## Sensitive Information

**⚠️ IMPORTANT: This repository does NOT contain any API keys, passwords, or sensitive credentials.**

All sensitive configuration is stored in environment variables that are:
- Listed in `.env.example` (template only, no real values)
- Loaded from `.env` (git-ignored, never committed)
- Required to be set by users during installation

## Protected Files

The following files are **git-ignored** and should NEVER be committed:

```
.env
.env.local
.env.docker
backend/.env
frontend/.env
**/secrets/
**/*secret*
**/*credential*
```

## Setup Instructions

### 1. Generate a Secret Key

```bash
# For Django SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 2. Obtain API Keys

- **OpenAI API Key**: Get from https://platform.openai.com/api-keys
- **Unstructured.io API Key** (optional): Get from https://unstructured.io

### 3. Create `.env` File

```bash
cp .env.example .env
# Edit .env with your actual values
```

**Never commit `.env` to version control!**

## Reporting Security Issues

If you discover a security vulnerability in this project, please email:

- **Do NOT** create a public GitHub issue
- Email: [your-email@example.com]
- Include: Description, reproduction steps, potential impact

## Best Practices for Contributors

1. **Never commit secrets**: Always use environment variables
2. **Check before pushing**: Run `git diff` to review changes
3. **Scan for leaks**: Use tools like `git-secrets` or `trufflehog`
4. **Rotate keys immediately** if accidentally exposed

## Dependencies

This project uses third-party packages. Security updates:

```bash
# Backend
pip install --upgrade -r requirements.txt

# Frontend
npm audit fix
```

## Production Deployment

For production use:

1. Set `DEBUG=False` in environment variables
2. Use strong, unique passwords for database
3. Enable HTTPS/TLS for all connections
4. Restrict `ALLOWED_HOSTS` to your domain
5. Use environment-specific `.env` files (never commit them)
6. Regularly rotate API keys and secrets
7. Enable database backup and encryption

## Changelog

- **2024-02**: Initial security policy created
- Repository sanitized to remove hardcoded secrets
