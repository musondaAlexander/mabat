"""Small, deliberate shared kernel used by every domain module.

Nothing in here may import a domain package, the snapshot composer or the CLI.
If this package starts growing quickly, that is a design smell — flag it.
"""
