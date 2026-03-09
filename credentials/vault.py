#!/usr/bin/env python3
"""
Credential Vault for Persistent Engineer Agent

Provides encrypted storage for credentials per workspace using Fernet (AES-128-CBC).
"""

import base64
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class CredentialVault:
    """Encrypted credential storage per workspace."""

    def __init__(self, base_path: str = '/workspace/.creds'):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Key file for encryption
        self.key_file = self.base_path / '.vault_key'

        # Initialize encryption key
        self._fernet = self._init_encryption()

    def _init_encryption(self) -> Fernet:
        """Initialize or load the encryption key."""
        if self.key_file.exists():
            # Load existing key
            key = self.key_file.read_bytes()
        else:
            # Generate new key
            key = Fernet.generate_key()
            self.key_file.write_bytes(key)
            # Restrict permissions
            os.chmod(self.key_file, 0o600)

        return Fernet(key)

    def _get_creds_file(self, workspace_name: str) -> Path:
        """Get the credentials file path for a workspace."""
        return self.base_path / f'{workspace_name}.enc'

    def _load_creds(self, workspace_name: str) -> Dict[str, str]:
        """Load and decrypt credentials for a workspace."""
        creds_file = self._get_creds_file(workspace_name)

        if not creds_file.exists():
            return {}

        try:
            encrypted_data = creds_file.read_bytes()
            decrypted_data = self._fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode('utf-8'))
        except Exception as e:
            # If decryption fails, return empty (corrupted file)
            return {}

    def _save_creds(self, workspace_name: str, creds: Dict[str, str]):
        """Encrypt and save credentials for a workspace."""
        creds_file = self._get_creds_file(workspace_name)

        json_data = json.dumps(creds).encode('utf-8')
        encrypted_data = self._fernet.encrypt(json_data)

        creds_file.write_bytes(encrypted_data)
        os.chmod(creds_file, 0o600)

    def get_workspace_credentials(self, workspace_name: str) -> Dict[str, str]:
        """
        Get all credentials for a workspace.

        Args:
            workspace_name: Name of the workspace

        Returns:
            Dictionary of credential name -> value
        """
        return self._load_creds(workspace_name)

    def set_credential(self, workspace_name: str, name: str, value: str):
        """
        Set a credential for a workspace.

        Args:
            workspace_name: Name of the workspace
            name: Credential name (e.g., 'GITHUB_TOKEN')
            value: Credential value
        """
        creds = self._load_creds(workspace_name)
        creds[name] = value
        self._save_creds(workspace_name, creds)

    def delete_credential(self, workspace_name: str, name: str):
        """
        Delete a credential from a workspace.

        Args:
            workspace_name: Name of the workspace
            name: Credential name to delete
        """
        creds = self._load_creds(workspace_name)
        if name in creds:
            del creds[name]
            self._save_creds(workspace_name, creds)

    def list_credentials(self, workspace_name: str) -> List[str]:
        """
        List credential names for a workspace (without values).

        Args:
            workspace_name: Name of the workspace

        Returns:
            List of credential names
        """
        creds = self._load_creds(workspace_name)
        return list(creds.keys())

    def delete_workspace_credentials(self, workspace_name: str):
        """
        Delete all credentials for a workspace.

        Args:
            workspace_name: Name of the workspace
        """
        creds_file = self._get_creds_file(workspace_name)
        if creds_file.exists():
            creds_file.unlink()

    def export_to_env(self, workspace_name: str) -> str:
        """
        Export credentials as environment variable exports.

        Args:
            workspace_name: Name of the workspace

        Returns:
            Shell script content with export statements
        """
        creds = self._load_creds(workspace_name)
        exports = []
        for name, value in creds.items():
            # Escape single quotes in value
            escaped_value = value.replace("'", "'\"'\"'")
            exports.append(f"export {name}='{escaped_value}'")
        return '\n'.join(exports)

    def inject_to_claude_md(self, workspace_name: str, claude_md_path: Path):
        """
        Inject credentials documentation into CLAUDE.md.

        Args:
            workspace_name: Name of the workspace
            claude_md_path: Path to the CLAUDE.md file
        """
        creds = self._load_creds(workspace_name)
        if not creds:
            return

        cred_section = "\n\n## Credentials (Auto-injected)\n\n"
        cred_section += "The following credentials are available as environment variables:\n\n"

        for name, value in creds.items():
            # Mask the value for security
            if len(value) > 8:
                masked = value[:4] + '...' + value[-4:]
            else:
                masked = '***'
            cred_section += f"- `{name}`: `{masked}`\n"

        cred_section += "\nAccess them via `os.environ['{name}']` or `${{name}}` in shell.\n"

        # Read existing CLAUDE.md or create new
        if claude_md_path.exists():
            content = claude_md_path.read_text()
            # Remove old credentials section if present
            marker = '## Credentials (Auto-injected)'
            if marker in content:
                parts = content.split(marker)
                content = parts[0].rstrip()
        else:
            content = "# Project Instructions\n"

        # Append credentials section
        claude_md_path.write_text(content + cred_section)


class MasterVault:
    """
    Master vault for agent-wide credentials (e.g., API keys).
    These are available across all workspaces.
    """

    def __init__(self, base_path: str = '/workspace/.creds'):
        self.vault = CredentialVault(base_path)
        self._master_workspace = '__master__'

    def get_all(self) -> Dict[str, str]:
        """Get all master credentials."""
        return self.vault.get_workspace_credentials(self._master_workspace)

    def set(self, name: str, value: str):
        """Set a master credential."""
        self.vault.set_credential(self._master_workspace, name, value)

    def delete(self, name: str):
        """Delete a master credential."""
        self.vault.delete_credential(self._master_workspace, name)

    def list(self) -> List[str]:
        """List master credential names."""
        return self.vault.list_credentials(self._master_workspace)
