#!/usr/bin/env bash
set -euo pipefail

echo "== Init: idea-to-action =="

echo ""
echo "== Current directory =="
pwd

echo ""
echo "== Repository files =="
ls -la

# Resolve python binary: prefer python3, fallback to python
if command -v python3 &>/dev/null; then
  PYTHON=python3
elif command -v python &>/dev/null; then
  PYTHON=python
else
  echo "ERROR: No python3 or python found in PATH."
  exit 1
fi

echo ""
echo "== Python version =="
$PYTHON --version

echo ""
echo "== Git status =="
if command -v git &>/dev/null && [ -d ".git" ]; then
  git log --oneline -5 2>/dev/null || echo "No commits yet."
  echo ""
  git status --short
else
  echo "Not a git repository or git not installed."
fi

echo ""
echo "== Dependency setup =="
if [ -f "pyproject.toml" ]; then
  echo "Found pyproject.toml"
  $PYTHON -m pip install -e ".[dev]" --quiet
elif [ -f "requirements.txt" ]; then
  echo "Found requirements.txt"
  $PYTHON -m pip install -r requirements.txt --quiet
else
  echo "No pyproject.toml or requirements.txt found. Skipping dependency install."
fi

echo ""
echo "== Environment check =="
if [ -n "${DEEPSEEK_API_KEY:-}" ]; then
  echo "OK: DEEPSEEK_API_KEY is set"
else
  echo "WARNING: DEEPSEEK_API_KEY is not set. LLM features will not work."
fi

echo ""
echo "== Baseline verification =="
if [ -d "tests" ]; then
  $PYTHON -m pytest -q
else
  echo "No tests/ directory found. Skipping pytest."
fi

echo ""
echo "== Eval check =="
if [ -f "scripts/run_evals.py" ]; then
  $PYTHON scripts/run_evals.py
else
  echo "No scripts/run_evals.py found. Skipping evals."
fi

echo ""
echo "== Run example =="
if [ -f "scripts/run_example.py" ]; then
  echo "Run:"
  echo "  $PYTHON scripts/run_example.py"
elif [ -f "examples/sample_ideas.txt" ]; then
  echo "Example input exists:"
  echo "  examples/sample_ideas.txt"
else
  echo "No runnable example found yet."
fi

echo ""
echo "== Required files check =="
for file in AGENTS.md ARCHITECTURE.md claude-progress.md feature_list.json; do
  if [ -f "$file" ]; then
    echo "OK: $file"
  else
    echo "MISSING: $file"
  fi
done

echo ""
echo "== Init complete =="
