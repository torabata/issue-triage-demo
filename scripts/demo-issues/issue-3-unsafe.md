The current password hashing implementation in `superset/security/manager.py` should be upgraded to use a stronger algorithm with a higher work factor.

## Scope

- Replace existing hash algorithm with bcrypt at higher cost factor
- Update password verification logic
- Migrate existing hashed passwords gracefully

## Acceptance criteria

- Existing user passwords continue to work after migration
- New passwords use stronger hashing
- All security-related tests pass
