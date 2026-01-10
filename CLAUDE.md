# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

This is a multi-project repository for storing and managing various projects created with Claude Code. Each project is organized in its own subdirectory.

## Repository Structure

- **Root directory**: Contains shared configuration files (.gitignore, README.md)
- **Project subdirectories**: Each project has its own directory with project-specific files and structure

## Working with Projects

When working on a specific project:
1. Navigate to the project's subdirectory
2. Check for project-specific README or documentation files
3. Look for package.json, requirements.txt, or other dependency files to understand the tech stack
4. Individual projects may have their own build, test, and run commands

## Git Workflow

This repository uses:
- **Main branch**: `main`
- **Remote**: `origin` at https://github.com/taiyosekiguchi/claude-code-projects.git
- **User**: taiyosekiguchi (tsekiguchi.k@gmail.com)

Standard Git workflow applies. Commit messages should be in Japanese to match the repository style.

## Important Notes

- .gitignore is configured for multiple tech stacks (Node.js, Python, macOS, various IDEs)
- Credentials and tokens are excluded from commits
- Each project in this repository is independent and may use different technologies
