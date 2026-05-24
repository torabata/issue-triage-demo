The functions in `superset/utils/date_parser.py` are missing type annotations. Adding them improves IDE support and type safety.

## Scope

- Add return type annotations to functions where missing
- Add parameter type annotations where missing
- Do not change any logic
- Do not change function signatures' semantics

## Acceptance criteria

- All function signatures have proper type hints
- `mypy` passes (if configured)
- No behavioral changes
