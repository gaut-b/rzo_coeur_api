# Project Context

rzo_coeur_api is a backend application built with Django. This project is the backend part of a project called "Le réSOS du coeur" (Heart Networks), whose principle is similar to the "pending coffee" but for food products.

The principle of this application is that "Client" users can purchase products in partner stores using the mobile application and leave them on the shelf. When these items are paid for, they appear in the list of available products for the partner social center to which the store is linked. "Social Center" users can then create baskets grouping several items from the same store and assign this basket to a "Recipient" user. The latter can then collect the items from the store and check out without paying for the products by showing the mobile application at the checkout.

This codebase is the backend part of the project, coded in Python using the Django framework. It exposes a REST API allowing the web application to retrieve information stored in the database, as well as a back office based on Django's admin interface to manage users and products scanned by the application (pending products, baskets...). PostgreSQL was chosen for its robustness, reliability and advanced features that suit well with Django's ORM.

## Data Models

The application uses the following Django models:

- **CustomUser**: Email-based authentication user model (replaces Django's default User)
- **Client**: Donor users who purchase products
- **Recipient**: Beneficiary users who receive baskets
- **Cashier**: Store cashiers who validate transactions
- **SocialWorker**: Social center staff who manage recipients and baskets
- **SocialCenter**: Social organizations managing recipients and linked to shops
- **Shop**: Partner stores where products are purchased and collected
- **Cart**: Baskets of articles assigned to recipients
- **Article**: Individual products purchased by clients

## User Roles and Permissions

We distinguish the following different types of users:

- **Client**:
  - Can create an account via the mobile application
  - Can retrieve the list of shops available in the application
  - Can purchase articles in one of the shops using the application during checkout

- **Recipient**:
  - Account is created by a social worker
  - Linked to a social center
  - Can retrieve carts assigned to them in a shop

- **Cashier**:
  - Linked to a shop
  - If shop admin, they can:
    - Create other cashier accounts linked to this shop via the admin interface
  - Has access to the list of all cashier users linked to their shop
  - Has access to the list of "suspended" articles in their shop
  - Has access to the list of carts created by their social center and their status (pending assignment, assigned to beneficiary, collected)
  - Validates article purchases when a client checks out
  - Validates cart withdrawal when a recipient checks out

- **SocialWorker**:
  - Linked to a social center
  - If social center admin, they can:
    - Create new shops and admin cashier users for it
    - Create social worker users linked to their social center
    - Create recipient users linked to their social center
  - Has access to the list of all recipients linked to their social center
  - Has access to the list of all social workers linked to their social center
  - Has access to the list of all shops linked to their social center
  - Has access to the list of available articles for each shop linked to their social center
  - Has access to the list of carts created by their social center and their status (pending, assigned, collected)
  - Can create new carts from the list of available articles in a shop linked to their social center and assign them to a recipient from their social center

# Python Coding Conventions

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (package and project manager)
- Django 5.x
- PostgreSQL

## Setup

```bash
# Install dependencies and create virtualenv (uv handles both)
uv sync

# Run management commands via uv
uv run python manage.py migrate
uv run python manage.py runserver
```

## Package Management

Dependencies are declared in `pyproject.toml` and locked in `uv.lock`. Always use `uv` to manage them — never `pip` directly.

```bash
# Add a production dependency
uv add <package>

# Add a development-only dependency
uv add --dev <package>

# Remove a dependency
uv remove <package>

# Run any command inside the project virtualenv
uv run <command>
```

## Python Instructions

- Write clear and concise comments for each function.
- Ensure functions have descriptive names and include type hints.
- Provide docstrings following PEP 257 conventions.
- Use the `typing` module for type annotations (e.g., `List[str]`, `Dict[str, int]`).
- Break down complex functions into smaller, more manageable functions.

## General Instructions

- Always prioritize readability and clarity.
- For algorithm-related code, include explanations of the approach used.
- Write code with good maintainability practices, including comments on why certain design decisions were made.
- Handle edge cases and write clear exception handling.
- For libraries or external dependencies, mention their usage and purpose in comments.
- Use consistent naming conventions and follow language-specific best practices.
- Write concise, efficient, and idiomatic code that is also easily understandable.

## Code Style and Formatting

- Follow the **PEP 8** style guide for Python.
- Maintain proper indentation (use 4 spaces for each level of indentation).
- Ensure lines do not exceed 79 characters.
- Place function and class docstrings immediately after the `def` or `class` keyword.
- Use blank lines to separate functions, classes, and code blocks where appropriate.

## Edge Cases and Testing

- Always include test cases for critical paths of the application.
- Account for common edge cases like empty inputs, invalid data types, and large datasets.
- Include comments for edge cases and the expected behavior in those cases.
- Write unit tests for functions and document them with docstrings explaining the test cases.

## Example of Proper Documentation

```python
def calculate_area(radius: float) -> float:
    """
    Calculate the area of a circle given the radius.

    Parameters:
    radius (float): The radius of the circle.

    Returns:
    float: The area of the circle, calculated as π * radius^2.
    """
    import math
    return math.pi * radius ** 2
```
