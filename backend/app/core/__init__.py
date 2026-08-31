"""Pure-Python core domain.

Modules in this package intentionally avoid importing web/database libraries
so they can be unit-tested in any environment. They encode the safety-critical
rules of the platform (trading modes, connection/data status).
"""
