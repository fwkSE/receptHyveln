# Contributing to ReceptHyveln

Thank you for your interest in contributing.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Adding support for a new site

If a recipe URL fails extraction, consider improving the generic HTML parsers in `app/section_parser.py` or `app/extractor.py`. Add a test fixture with a minimal HTML snippet that reproduces the site structure.

Run `pytest` and open a pull request.

## Code style

- Keep changes focused and match existing patterns in the codebase.
- Add tests for real parsing behaviour, not trivial assertions.
- Do not commit secrets, `.env` files, or local virtualenvs.

## License

By contributing, you agree that your contributions will be licensed under the same [GPLv3](LICENSE) license as the project.
