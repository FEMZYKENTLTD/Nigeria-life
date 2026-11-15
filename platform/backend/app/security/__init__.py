"""AuthN/AuthZ for the multi-user deployment.

Local-first behaviour is preserved: when Supabase Auth is NOT configured
(``RICE_SUPABASE_URL`` + ``RICE_SUPABASE_JWT_SECRET`` absent) the platform
runs as a single implicit local admin — exactly as before this layer
existed, and every existing test keeps working unchanged.

When Supabase IS configured, every API request must carry a valid
``Authorization: Bearer <jwt>`` issued by Supabase Auth. The token is
verified (HS256, the Supabase default) and mapped onto a ``profiles`` row
(roles: ``admin`` | ``member``). Data ownership is enforced per project
(``projects.owner_id``); admins see everything, members see only their own
projects. Unknown/forbidden projects return 404, not 403 — existence is not
leaked across users.
"""
