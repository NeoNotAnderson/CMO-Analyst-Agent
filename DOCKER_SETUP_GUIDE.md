# Docker Setup Guide for CMO Analyst Agent

## Prerequisites

### Install Docker Desktop (if not already installed)

1. **Download**: https://www.docker.com/products/docker-desktop/
2. **Install**: Drag to Applications folder
3. **Launch**: Open Docker Desktop
4. **Wait**: Until you see the whale icon in menu bar (green means running)

### Verify Docker Installation

```bash
docker --version
# Should output: Docker version 24.x.x or higher

docker-compose --version
# Should output: Docker Compose version v2.x.x or higher
```

---

## Quick Start (After Docker is Installed)

### Step 1: Create Environment File

Copy the example environment file and update with your settings:

```bash
cd /Users/yugao/Desktop/project/CMO-Analyst-Agent
cp .env.example backend/.env
```

Edit `backend/.env` and add your API keys:
- `OPENAI_API_KEY` - Your OpenAI API key
- `SECRET_KEY` - Generate a random secret key

### Step 2: Start PostgreSQL

From the project root directory:

```bash
docker-compose up -d
```

This will:
- Download PostgreSQL 15 image (first time only)
- Start PostgreSQL container
- Create database `cmo_analyst_db`
- Expose on port 5432

### Step 3: Verify Database is Running

```bash
# Check container status
docker-compose ps

# Should see:
# NAME              STATUS    PORTS
# cmo_analyst_db    Up        0.0.0.0:5432->5432/tcp
```

Test database connection:

```bash
docker-compose exec db psql -U cmo_user -d cmo_analyst_db -c "SELECT version();"
```

Should display PostgreSQL version information.

---

## Docker Commands Cheat Sheet

### Start Database
```bash
docker-compose up -d
```

### Stop Database
```bash
docker-compose down
```

### Stop and Remove All Data (CAREFUL!)
```bash
docker-compose down -v
```

### View Logs
```bash
docker-compose logs db
docker-compose logs -f db  # Follow logs in real-time
```

### Access PostgreSQL Shell
```bash
docker-compose exec db psql -U cmo_user -d cmo_analyst_db
```

Inside PostgreSQL shell:
```sql
-- List databases
\l

-- Connect to database
\c cmo_analyst_db

-- List tables
\dt

-- Describe a table
\d table_name

-- Exit
\q
```

### Check Container Status
```bash
docker-compose ps
```

### Restart Database
```bash
docker-compose restart db
```

---

## Database Configuration Details

**Connection Parameters** (use these in Django settings):

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'cmo_analyst_db',
        'USER': 'cmo_user',
        'PASSWORD': 'cmo_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

**Connection String** (for other tools):
```
postgresql://cmo_user:cmo_password@localhost:5432/cmo_analyst_db
```

---

## Troubleshooting

### Port 5432 Already in Use

If you have another PostgreSQL instance running:

```bash
# Find what's using port 5432
lsof -i :5432

# Stop local PostgreSQL if installed
brew services stop postgresql
```

Or change the port in `docker-compose.yml`:
```yaml
ports:
  - "5433:5432"  # Use 5433 on your Mac, 5432 in container
```

### Container Won't Start

Check logs:
```bash
docker-compose logs db
```

Remove and recreate:
```bash
docker-compose down
docker-compose up -d
```

### Connection Refused

Make sure Docker Desktop is running and container is healthy:
```bash
docker-compose ps
# STATUS should show "Up (healthy)"
```

### Reset Everything

Complete cleanup:
```bash
docker-compose down -v
docker volume prune
docker-compose up -d
```

---

## Data Persistence

Database data is stored in a Docker volume named `postgres_data`.

- **Data persists** even when container is stopped/restarted
- **Data is deleted** only when you run `docker-compose down -v`

View volumes:
```bash
docker volume ls
```

Backup database:
```bash
docker-compose exec db pg_dump -U cmo_user cmo_analyst_db > backup.sql
```

Restore database:
```bash
cat backup.sql | docker-compose exec -T db psql -U cmo_user cmo_analyst_db
```

---

## Next Steps

Once PostgreSQL is running:

1. ✅ Create Django project
2. ✅ Configure database in `settings.py`
3. ✅ Run migrations: `python manage.py migrate`
4. ✅ Create superuser: `python manage.py createsuperuser`
5. ✅ Start development!

---

## Production Notes

For production deployment, you should:

1. **Change passwords** in `docker-compose.yml`
2. **Use environment variables** instead of hardcoded values
3. **Enable SSL** for database connections
4. **Set up regular backups**
5. **Use managed PostgreSQL** (AWS RDS, Google Cloud SQL, etc.)

This docker-compose setup is for **development only**!
