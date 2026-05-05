"""
signature_inspector.py — Inspect digital signatures in files.
"""

from __future__ import annotations
import platform
import subprocess
import os
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class SignatureInfo:
    is_signed: bool
    is_valid: bool = False
    signer_name: Optional[str] = None
    issuer_name: Optional[str] = None
    serial_number: Optional[str] = None
    thumbprint: Optional[str] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    signature_type: Optional[str] = None
    error_message: Optional[str] = None


def inspect_signature_windows(file_path: str) -> SignatureInfo:
    """
    Inspect Authenticode signature on Windows using sigcheck.exe or PowerShell.
    """
    if platform.system() != "Windows":
        return SignatureInfo(is_signed=False, error_message="Signature inspection only available on Windows")

    # Try using PowerShell first (built-in)
    try:
        cmd = [
            "powershell", "-Command",
            f"Get-AuthenticodeSignature '{file_path}' | ConvertTo-Json"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode == 0 and result.stdout.strip():
            import json
            data = json.loads(result.stdout)

            is_signed = data.get("Status") != "NotSigned"
            is_valid = data.get("Status") == "Valid"

            signer = data.get("SignerCertificate", {})
            issuer = signer.get("Issuer", "")

            return SignatureInfo(
                is_signed=is_signed,
                is_valid=is_valid,
                signer_name=signer.get("Subject"),
                issuer_name=issuer,
                serial_number=signer.get("SerialNumber"),
                thumbprint=signer.get("Thumbprint"),
                valid_from=signer.get("NotBefore"),
                valid_to=signer.get("NotAfter"),
                signature_type="Authenticode"
            )

    except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError, FileNotFoundError):
        pass

    # Fallback: try sigcheck.exe if available
    try:
        # Look for sigcheck in common locations
        sigcheck_paths = [
            "C:\\Sysinternals\\sigcheck.exe",
            "C:\\SysinternalsSuite\\sigcheck.exe",
            os.path.join(os.environ.get("Program Files", ""), "Sysinternals", "sigcheck.exe")
        ]

        sigcheck_exe = None
        for path in sigcheck_paths:
            if os.path.exists(path):
                sigcheck_exe = path
                break

        if sigcheck_exe:
            result = subprocess.run([sigcheck_exe, "-accepteula", file_path], capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    if "Verified:" in line:
                        is_signed = "Signed" in line
                        is_valid = "OK" in line or "Valid" in line
                        return SignatureInfo(is_signed=is_signed, is_valid=is_valid, signature_type="Authenticode")

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return SignatureInfo(is_signed=False, error_message="Could not inspect signature")
    
def inspect_signature(file_path: str) -> SignatureInfo:
    """
    Inspect digital signature of a file.
    Currently supports Authenticode on Windows.
    """
    if not os.path.exists(file_path):
        return SignatureInfo(is_signed=False, error_message="File does not exist")

    if platform.system() == "Windows":
        return inspect_signature_windows(file_path)
    else:
        return SignatureInfo(is_signed=False, error_message="Signature inspection not supported on this platform")

def check_pgp_signature(file_path: str, sig_file_path: Optional[str] = None) -> SignatureInfo:
    """
    Check for PGP/GPG signature.
    """
    if not sig_file_path:
        # Look for .sig or .asc file
        base_path = os.path.splitext(file_path)[0]
        for ext in [".sig", ".asc", ".gpg"]:
            potential_sig = base_path + ext
            if os.path.exists(potential_sig):
                sig_file_path = potential_sig
                break

    if not sig_file_path or not os.path.exists(sig_file_path):
        return SignatureInfo(is_signed=False, error_message="No signature file found")

    try:
        # Try to verify with GPG
        result = subprocess.run(["gpg", "--verify", sig_file_path, file_path], capture_output=True, text=True, timeout=30)

        is_valid = result.returncode == 0

        # Extract signer info from output
        signer_name = None
        if result.stderr:
            lines = result.stderr.split('\n')
            for line in lines:
                if "Good signature from" in line:
                    # Extract name from "Good signature from "Name" <email>"
                    import re
                    match = re.search(r'Good signature from "([^"]*)"', line)
                    if match:
                        signer_name = match.group(1)
                    break

        return SignatureInfo(
            is_signed=True,
            is_valid=is_valid,
            signer_name=signer_name,
            signature_type="PGP/GPG",
            error_message=result.stderr if not is_valid else None
        )

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return SignatureInfo(is_signed=False, error_message="GPG not available or signature verification failed")