#!/usr/bin/env python3
"""
Auto-detection for build commands and test URLs

Detects the project type and automatically configures:
- Build command based on project files
- Test URL based on common dev server ports and config
"""

import json
import os
from pathlib import Path


def detect_build_command():
    """Auto-detect the build command based on project files"""
    cwd = Path.cwd()

    # Node.js / JavaScript / TypeScript
    package_json = cwd / "package.json"
    if package_json.exists():
        try:
            with open(package_json) as f:
                pkg = json.load(f)
                scripts = pkg.get("scripts", {})

            # Check for common build scripts in priority order
            if "build" in scripts:
                # Determine package manager
                if (cwd / "pnpm-lock.yaml").exists():
                    return "pnpm run build"
                elif (cwd / "yarn.lock").exists():
                    return "yarn build"
                elif (cwd / "bun.lockb").exists():
                    return "bun run build"
                else:
                    return "npm run build"

            # Check for test script
            if "test" in scripts:
                if (cwd / "pnpm-lock.yaml").exists():
                    return "pnpm test"
                elif (cwd / "yarn.lock").exists():
                    return "yarn test"
                else:
                    return "npm test"

            # TypeScript project without build script
            if (cwd / "tsconfig.json").exists():
                return "npx tsc"

        except Exception:
            pass

    # Python
    if (cwd / "pyproject.toml").exists() or (cwd / "setup.py").exists():
        # Check for common Python test commands
        if (cwd / "pytest.ini").exists() or (cwd / "tests").exists():
            return "pytest"
        if (cwd / "setup.py").exists():
            return "python setup.py build"
        return "python -m build"

    if (cwd / "requirements.txt").exists():
        return "pytest" if (cwd / "tests").exists() else "python -m py_compile *.py"

    # Go
    if (cwd / "go.mod").exists():
        return "go build ./... && go test ./..."

    # Rust
    if (cwd / "Cargo.toml").exists():
        return "cargo build"

    # Java - Maven
    if (cwd / "pom.xml").exists():
        return "mvn clean install"

    # Java - Gradle
    if (cwd / "build.gradle").exists() or (cwd / "build.gradle.kts").exists():
        return "./gradlew build"

    # C# / .NET
    if list(cwd.glob("*.csproj")) or list(cwd.glob("*.sln")):
        return "dotnet build"

    # Ruby
    if (cwd / "Gemfile").exists():
        return "bundle exec rake" if (cwd / "Rakefile").exists() else "ruby -c *.rb"

    # PHP
    if (cwd / "composer.json").exists():
        return "composer install && vendor/bin/phpunit" if (cwd / "phpunit.xml").exists() else "php -l *.php"

    # Default fallback
    return "npm run build"


def detect_test_url():
    """Auto-detect the test URL based on project config and common patterns"""
    cwd = Path.cwd()

    # Node.js - check package.json for dev server config
    package_json = cwd / "package.json"
    if package_json.exists():
        try:
            with open(package_json) as f:
                pkg = json.load(f)

            # Check for port in various places
            scripts = pkg.get("scripts", {})

            # Vite (look for --port or port in vite.config)
            if "dev" in scripts and "vite" in scripts["dev"]:
                vite_config = cwd / "vite.config.js"
                vite_config_ts = cwd / "vite.config.ts"
                if vite_config.exists() or vite_config_ts.exists():
                    # Vite default is 5173
                    return "http://localhost:5173"

            # Next.js
            if "next" in pkg.get("dependencies", {}) or "next" in pkg.get("devDependencies", {}):
                return "http://localhost:3000"

            # Create React App
            if "react-scripts" in pkg.get("dependencies", {}) or "react-scripts" in pkg.get("devDependencies", {}):
                return "http://localhost:3000"

            # Vue CLI
            if "@vue/cli-service" in pkg.get("devDependencies", {}):
                return "http://localhost:8080"

            # Angular
            if "@angular/cli" in pkg.get("devDependencies", {}):
                return "http://localhost:4200"

            # Svelte
            if "svelte" in pkg.get("dependencies", {}) or "svelte" in pkg.get("devDependencies", {}):
                return "http://localhost:5173"

        except Exception:
            pass

    # Python - Flask
    if (cwd / "app.py").exists() or (cwd / "wsgi.py").exists():
        return "http://localhost:5000"

    # Python - Django
    if (cwd / "manage.py").exists():
        return "http://localhost:8000"

    # Python - FastAPI
    if list(cwd.glob("**/main.py")):
        return "http://localhost:8000"

    # Go
    if (cwd / "go.mod").exists():
        return "http://localhost:8080"

    # Rust - check for web frameworks
    cargo_toml = cwd / "Cargo.toml"
    if cargo_toml.exists():
        try:
            content = cargo_toml.read_text()
            if "actix-web" in content or "rocket" in content or "warp" in content:
                return "http://localhost:8080"
        except Exception:
            pass

    # Ruby on Rails
    if (cwd / "Gemfile").exists():
        try:
            gemfile = (cwd / "Gemfile").read_text()
            if "rails" in gemfile:
                return "http://localhost:3000"
        except Exception:
            pass

    # PHP
    if (cwd / "index.php").exists() or (cwd / "public" / "index.php").exists():
        return "http://localhost:8000"

    # Java Spring Boot
    if (cwd / "pom.xml").exists():
        try:
            pom = (cwd / "pom.xml").read_text()
            if "spring-boot" in pom:
                return "http://localhost:8080"
        except Exception:
            pass

    # Default fallback - most common dev server port
    return "http://localhost:3000"


def auto_detect_config():
    """Auto-detect both build command and test URL"""
    return {
        "build_command": detect_build_command(),
        "test_url": detect_test_url()
    }


if __name__ == "__main__":
    # For testing
    config = auto_detect_config()
    print(json.dumps(config, indent=2))
