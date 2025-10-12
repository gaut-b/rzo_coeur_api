# Project Context

rzo_coeur_api is a backend application built with Django. This project is the backend part of a project called "Les réseaux du coeur" (Heart Networks), whose principle is similar to the "pending coffee" but for food products.

The principle of this application is that "Donor" users can purchase products in partner stores using the mobile application and leave them on the shelf. When these items are paid for, they appear in the list of available products for the partner social center to which the store is linked. "Social Center" users can then create baskets grouping several items from the same store and assign this basket to a "Beneficiary" user. The latter can then collect the items from the store and check out without paying for the products by showing the mobile application at the checkout.

This codebase is the backend part of the project, coded in Python using the Django framework. It exposes a REST API allowing the web application to retrieve information stored in the database, as well as a back office based on Django's admin interface to manage users and products scanned by the application (pending products, baskets...). PostgreSQL was chosen for its robustness, reliability and advanced features that suit well with Django's ORM.

We distinguish the following different types of users:

- Donor:

  - Can create an account via the mobile application
  - Can retrieve the list of stores available in the application
  - Can purchase items in one of the stores using the application during checkout

- Beneficiary:

  - Account is created by a social worker
  - Can retrieve baskets assigned to them in a store

- Cashier:

  - Linked to a store
  - If store admin, they can:
    - Create other cashier accounts linked to this store via the admin interface
  - Has access to the list of all "Cashier" users linked to their store
  - Has access to the list of "suspended" items in their store
  - Has access to the list of baskets created by their social center and their status (pending assignment, pending collection, collected)
  - Validates item purchases when a "Donor" user checks out
  - Validates basket withdrawal when a "Beneficiary" user checks out

- Social Worker:
  - Linked to a social center
  - If social center admin, they can:
    - Create new stores and admin "Cashier" users for it
    - Create "Social Worker" users linked to their social center
    - Create "Beneficiary" users linked to their social center
  - Has access to the list of all beneficiaries linked to their social center
  - Has access to the list of all social workers linked to their social center
  - Has access to the list of all stores linked to their social center
  - Has access to the list of available items for each store linked to their social center
  - Has access to the list of baskets created by their social center and their status (pending assignment, pending collection, collected)
  - Can create new baskets from the list of available items in a store linked to their social center and assign them to a "Beneficiary" from their social center

# Python Coding Conventions

## Prerequisites

- Python 3.8+
- Django 4.x
- PostgreSQL

## Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Database configuration
python manage.py migrate
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
