"""Cross-cutting infrastructure shared by every feature module.

Nothing in `core` may import from `backend.modules.*` -- the dependency arrow
points one way only (modules -> core). That rule is what keeps the modular
monolith from collapsing back into the single 963-line file it replaced.
"""
