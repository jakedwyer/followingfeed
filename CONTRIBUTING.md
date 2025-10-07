# Contributing to FollowFeed

Thank you for your interest in contributing to FollowFeed! This document provides guidelines for contributing to the project.

## Code of Conduct

Be respectful, inclusive, and professional in all interactions.

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in GitHub Issues
2. If not, create a new issue with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python version, etc.)
   - Relevant logs or error messages

### Suggesting Features

1. Check if the feature has been suggested already
2. Create an issue describing:
   - The problem it solves
   - Proposed solution
   - Alternative solutions considered
   - Additional context

### Pull Requests

1. Fork the repository
2. Create a feature branch from `main`
3. Make your changes
4. Write/update tests as needed
5. Ensure all tests pass
6. Update documentation
7. Submit a pull request

#### PR Guidelines

- Keep PRs focused on a single feature/fix
- Write clear commit messages
- Include tests for new functionality
- Update README if adding features
- Follow existing code style
- Add docstrings to new functions

## Development Setup

```bash
# Clone your fork
git clone https://github.com/yourusername/followfeed.git
cd followfeed

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest black isort mypy

# Run tests
pytest
```

## Code Style

- Follow PEP 8
- Use type hints where appropriate
- Write docstrings for functions and classes
- Keep functions focused and small
- Use meaningful variable names

### Formatting

```bash
# Format code
black .
isort .

# Check types
mypy .
```

## Testing

- Write tests for new features
- Ensure existing tests pass
- Aim for good test coverage

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html
```

## Documentation

- Update README.md for user-facing changes
- Add docstrings to new functions
- Update .env.example for new config options
- Add comments for complex logic

## Questions?

Feel free to open an issue for questions or clarifications!

Thank you for contributing! 🎉
