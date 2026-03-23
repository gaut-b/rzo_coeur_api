"""
Admin discovery module.

Django discovers this file via app auto-discovery. It triggers the
registration of all domain-specific admin classes by importing each
domain's admin module.
"""

import api.articles.admin  # noqa: F401
import api.carts.admin  # noqa: F401
import api.shops.admin  # noqa: F401
import api.social.admin  # noqa: F401
import api.users.admin  # noqa: F401
