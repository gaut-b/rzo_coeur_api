"""
Application-level constants and configurable limits.
These values can be overridden via environment variables.
"""

import os

# Maximum number of articles that can be created in a single bulk request
# Default: 10 articles per request
# Can be overridden by setting the MAX_ARTICLES_PER_REQUEST environment variable
MAX_ARTICLES_PER_REQUEST = int(os.environ.get("MAX_ARTICLES_PER_REQUEST", "10"))
