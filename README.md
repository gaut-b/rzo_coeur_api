<h1 align="center">
  <img alt="logo" src="./assets/icon.png" width="124px" style="border-radius:10px"/><br/>
Les réseaux du coeur (backend)</h1>

rzo_coeur_api is a backend application built with Django. This project is the backend part of a project called “Les réseaux du coeur”, whose principle is similar to the "pending coffee" but for food products.

The mobile apps of the project can be found [on this repo](https://github.com/gaut-b/reseau-coeur-mobile-app)

## Requirements

- [Docker](https://docs.docker.com/get-docker/)

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

## Environment Variables

The following environment variables can be configured in your `.env` file:

### Database Configuration
- `SQL_ENGINE` - Database engine (default: `django.db.backends.postgresql`)
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

## Contributors

- [Clement Viel](https://github.com/ClementViel)
- [Gautier Bayle](https://github.com/gaut-b)
