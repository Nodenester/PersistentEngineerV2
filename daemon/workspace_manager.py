#!/usr/bin/env python3
"""
Workspace Manager for Persistent Engineer Agent

Manages multiple project workspaces under /workspace/projects/,
including cloning, switching, and credential management.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional


class WorkspaceManager:
    """Manages multiple project workspaces."""

    def __init__(self, base_path: str = '/workspace/projects'):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Workspace metadata file
        self.metadata_file = self.base_path / '.workspaces.json'

        # Credentials directory
        self.creds_base = Path('/workspace/.creds')
        self.creds_base.mkdir(parents=True, exist_ok=True)

    def _load_metadata(self) -> Dict:
        """Load workspace metadata."""
        if self.metadata_file.exists():
            return json.loads(self.metadata_file.read_text())
        return {'workspaces': {}}

    def _save_metadata(self, metadata: Dict):
        """Save workspace metadata."""
        self.metadata_file.write_text(json.dumps(metadata, indent=2))

    def create_workspace(self, name: str, repo_url: str, branch: str = 'main', github_token: str = None) -> Path:
        """
        Create a new workspace by cloning a Git repository.

        Args:
            name: Unique name for the workspace
            repo_url: Git repository URL
            branch: Branch to checkout (default: main)
            github_token: Optional GitHub token for private repositories

        Returns:
            Path to the workspace directory
        """
        workspace_path = self.base_path / name

        if workspace_path.exists():
            raise ValueError(f"Workspace '{name}' already exists")

        # If github_token provided, inject it into the URL for private repos
        clone_url = repo_url
        if github_token and 'github.com' in repo_url:
            # Convert https://github.com/user/repo to https://TOKEN@github.com/user/repo
            clone_url = repo_url.replace('https://github.com', f'https://{github_token}@github.com')

        # Clone the repository
        result = subprocess.run(
            ['git', 'clone', '--branch', branch, clone_url, str(workspace_path)],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            # Try without branch (might be default branch)
            result = subprocess.run(
                ['git', 'clone', clone_url, str(workspace_path)],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                raise RuntimeError(f"Failed to clone repository: {result.stderr}")

        # Update metadata
        metadata = self._load_metadata()
        metadata['workspaces'][name] = {
            'path': str(workspace_path),
            'repo_url': repo_url,
            'branch': branch,
            'created_at': self._now()
        }
        self._save_metadata(metadata)

        # Create credentials file for this workspace
        creds_file = self.creds_base / f'{name}.json'
        if not creds_file.exists():
            creds_file.write_text('{}')

        return workspace_path

    def delete_workspace(self, name: str):
        """
        Delete a workspace and its associated data.

        Args:
            name: Name of the workspace to delete
        """
        workspace_path = self.base_path / name

        if not workspace_path.exists():
            raise ValueError(f"Workspace '{name}' does not exist")

        # Remove the directory
        shutil.rmtree(workspace_path)

        # Update metadata
        metadata = self._load_metadata()
        if name in metadata['workspaces']:
            del metadata['workspaces'][name]
        self._save_metadata(metadata)

        # Remove credentials
        creds_file = self.creds_base / f'{name}.json'
        if creds_file.exists():
            creds_file.unlink()

    def workspace_exists(self, name: str) -> bool:
        """Check if a workspace exists."""
        return (self.base_path / name).exists()

    def get_workspace_path(self, name: str) -> Path:
        """Get the path to a workspace."""
        workspace_path = self.base_path / name
        if not workspace_path.exists():
            raise ValueError(f"Workspace '{name}' does not exist")
        return workspace_path

    def list_workspaces(self) -> List[Dict]:
        """List all workspaces with their metadata."""
        metadata = self._load_metadata()
        workspaces = []

        for name, info in metadata['workspaces'].items():
            workspace_path = self.base_path / name
            if workspace_path.exists():
                # Get current branch
                try:
                    result = subprocess.run(
                        ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                        cwd=str(workspace_path),
                        capture_output=True,
                        text=True
                    )
                    current_branch = result.stdout.strip() if result.returncode == 0 else 'unknown'
                except:
                    current_branch = 'unknown'

                workspaces.append({
                    'name': name,
                    'path': str(workspace_path),
                    'repo_url': info.get('repo_url', ''),
                    'branch': current_branch,
                    'created_at': info.get('created_at', '')
                })

        return workspaces

    def get_credentials(self, workspace_name: str) -> Dict[str, str]:
        """
        Get credentials for a workspace.

        Args:
            workspace_name: Name of the workspace

        Returns:
            Dictionary of credential name -> value
        """
        from credentials.vault import CredentialVault

        vault = CredentialVault()
        return vault.get_workspace_credentials(workspace_name)

    def set_credential(self, workspace_name: str, name: str, value: str):
        """
        Set a credential for a workspace.

        Args:
            workspace_name: Name of the workspace
            name: Credential name (e.g., 'GITHUB_TOKEN')
            value: Credential value
        """
        from credentials.vault import CredentialVault

        vault = CredentialVault()
        vault.set_credential(workspace_name, name, value)

    def delete_credential(self, workspace_name: str, name: str):
        """
        Delete a credential from a workspace.

        Args:
            workspace_name: Name of the workspace
            name: Credential name to delete
        """
        from credentials.vault import CredentialVault

        vault = CredentialVault()
        vault.delete_credential(workspace_name, name)

    def git_pull(self, name: str) -> str:
        """Pull latest changes for a workspace."""
        workspace_path = self.get_workspace_path(name)
        result = subprocess.run(
            ['git', 'pull'],
            cwd=str(workspace_path),
            capture_output=True,
            text=True
        )
        return result.stdout + result.stderr

    def git_status(self, name: str) -> str:
        """Get git status for a workspace."""
        workspace_path = self.get_workspace_path(name)
        result = subprocess.run(
            ['git', 'status', '--short'],
            cwd=str(workspace_path),
            capture_output=True,
            text=True
        )
        return result.stdout

    @staticmethod
    def _now() -> str:
        """Get current timestamp as ISO string."""
        from datetime import datetime
        return datetime.utcnow().isoformat()
