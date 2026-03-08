<h1 align="center">
  <img alt="logo" src="./assets/icon.png" width="124px" style="border-radius:10px"/><br/>
Les réseaux du coeur (backend)</h1>

rzo_coeur_api is a backend application built with Django. This project is the backend part of a project called “Les réseaux du coeur”, whose principle is similar to the "pending coffee" but for food products.

The mobile apps of the project can be found [on this repo](https://github.com/gaut-b/reseau-coeur-mobile-app)

## Requirements

### With Docker (Recommended)

- [Docker](https://docs.docker.com/get-docker/)
- [uv](https://docs.astral.sh/uv/) (optional, for local development)
- [PostgreSQL](https://www.postgresql.org/) with [PostGIS](https://postgis.net/) extension (automatically configured in Docker)

## 🚀 Quick start

Clone the repo to your machine:

```sh
git clone https://github.com/gaut-b/rzo_coeur_api.git
```

To launch the development server:

```sh
docker compose up --watch --build
```

To launch only the database:

```sh
docker compose up db
```

## Local Development (without Docker)

If you prefer to develop locally without Docker:

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/):

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Install dependencies (uses `uv.lock` for reproducible builds):

```sh
uv sync
```

This will create a virtual environment and install all dependencies from the lock file.

3. Install GDAL and GEOS

for macOS:

```sh
brew install gdal geos
```

For Ubuntu/Debian

```sh
sudo apt-get update
sudo apt-get install gdal-bin libgdal-dev libgeos-dev
```

4. Set up your `.env` file with the required environment variables (see below)

5. Run migrations and start the server:

```sh
uv run python manage.py migrate
uv run python manage.py runserver
```

**Development tools**: To install dev dependencies (ruff, mypy, etc.):

```sh
uv sync --group dev
```

## Environment Variables

The following environment variables can be configured in your `.env` file:

### Database Configuration

- `SQL_ENGINE` - Database engine (must be `django.contrib.gis.db.backends.postgis` for PostGIS support)
- `SQL_DATABASE` - Database name
- `SQL_USER` - Database user
- `SQL_PASSWORD` - Database password
- `SQL_HOST` - Database host
- `SQL_PORT` - Database port

### API Configuration

- `MAX_ARTICLES_PER_REQUEST` - Maximum number of articles that can be created in a single bulk request (default: `50`)

### Django Configuration

- `DEBUG` - Enable debug mode (`1` for True, `0` for False)
- `SECRET_KEY` - Django secret key
- `ALLOWED_HOSTS` - Comma-separated list of allowed hosts

### Email Configuration (Development)

- `EMAIL_HOST` - SMTP host for email sending (default: `localhost` for local dev, `mailhog` for Docker)
- `EMAIL_PORT` - SMTP port (default: `1025` for Mailhog)

## 📧 Email Testing with Mailhog

In development mode, emails are captured by [Mailhog](https://github.com/mailhog/MailHog) instead of being sent to real addresses. This allows you to test email functionality without worrying about accidentally sending emails.

### Accessing Mailhog

When running with Docker Compose, Mailhog is automatically started. Access the web interface at:

**http://localhost:8025**

All emails sent by the Django application will appear in this interface.

### Configuration

The email configuration is automatically handled:

- **With Docker**: Uses `EMAIL_HOST=mailhog` (configured in `.env`)
- **Without Docker**: Uses `EMAIL_HOST=localhost` and requires Mailhog running locally

To run Mailhog standalone (without Docker):

```sh
docker run -d -p 1025:1025 -p 8025:8025 mailhog/mailhog
```

## Tests

### Unit tests (Django)

The unit test suite runs against the Django ORM directly via `manage.py test`.

```sh
uv run python manage.py test
```

### E2E tests (Playwright)

The E2E test suite exercises the four admin interfaces in a real browser using [Playwright](https://playwright.dev/python/) and [pytest-playwright](https://playwright.dev/python/docs/test-runners).

**Covered flows**

| Interface        | Flows tested                                                                                                                        |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `/admin/`        | Non-staff users are denied access                                                                                                   |
| `/social-admin/` | Social admin can log in; social worker is denied; creation of recipients and social workers                                         |
| `/cart-admin/`   | Social admin and social workers can log in; view available articles; create a cart; assign/remove articles                          |
| `/shop-admin/`   | Non-cashiers are denied; cashiers can view articles but cannot manage cashiers; shop managers can view articles and create cashiers |

#### Prerequisites

Install dev dependencies (includes Playwright) and the Chromium browser:

```sh
uv sync --group dev
uv run playwright install chromium
```

#### Running the tests

```sh
uv run pytest e2e/ -p no:django -v
```

The test session is fully self-contained and runs against a production-like stack:

1. The full application is built and started via `docker-compose.e2e.yml`: **nginx + backend (gunicorn) + PostGIS + MinIO** — identical to production.
2. `docker compose --wait` blocks until every healthcheck passes (backend ready, DB ready, MinIO ready).
3. E2E seed data is loaded directly into the running backend container (`docker compose exec`).
4. All tests run against nginx on port **8001**.
5. The entire stack (containers + volumes) is destroyed when the session ends.

To watch the tests run in a real browser window, add `--headed` (and optionally `--slowmo` in milliseconds):

```sh
uv run pytest e2e/ -p no:django -v --headed --slowmo=500
```

To target a pre-running stack (skips Docker lifecycle):

```sh
E2E_EXTERNAL_STACK=1 E2E_BASE_URL=http://127.0.0.1:8001 uv run pytest e2e/ -p no:django -v
```

#### CI mode

In CI pipelines that build and start the stack as a separate step, set `E2E_EXTERNAL_STACK=1` to skip the Docker lifecycle management:

```sh
E2E_EXTERNAL_STACK=1 uv run pytest e2e/ -p no:django -v
```

#### E2E test data

The seed command creates a fixed, idempotent set of users and data:

| Role          | Email                          |
| ------------- | ------------------------------ |
| Social admin  | `e2e-social-admin@test.local`  |
| Social worker | `e2e-social-worker@test.local` |
| Shop manager  | `e2e-shop-manager@test.local`  |
| Cashier       | `e2e-cashier@test.local`       |
| Recipient     | `e2e-recipient@test.local`     |

It can also be run independently:

```sh
uv run python manage.py seed_data --env e2e
```

#### Development data

To populate the database with realistic sample data for local development:

```sh
uv run python manage.py seed_data          # defaults to --env dev
uv run python manage.py seed_data --env dev
```

Fixture files live in `api/fixtures/dev/` (one JSON file per entity type).
Add or edit entries in those files to extend the dataset without touching Python code.

## Contributors

- [Clement Viel](https://github.com/ClementViel)
- [Gautier Bayle](https://github.com/gaut-b)
