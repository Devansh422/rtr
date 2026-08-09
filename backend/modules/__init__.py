"""Feature modules.

Each module owns one bounded slice of the platform: its own router, its own
schemas and its own persistence. Modules import from `backend.core`; they do not
import from each other. When two modules genuinely need to share behaviour, the
shared part moves down into core rather than sideways across the boundary.

This is a modular monolith, not microservices -- one deployable, clean seams
inside it. Splitting a module out into its own service later is then a matter of
moving a directory, not untangling a call graph.
"""
