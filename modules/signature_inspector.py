"""
signature_inspector.py — Inspect digital signatures in files.
"""

from __future__ import annotations
import platform
import subprocess
import os
import re
import json
import shutil
from typing import Optional
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
        return SignatureInfo(
            is_signed=False,
            error_message="Signature inspection only available on Windows",
        )

    # Try using PowerShell first (built-in).
    # The path is passed via an environment variable + -LiteralPath, so quotes,
    # brackets or `$` in a filename can neither break nor inject into the command.
    try:
        script = (
            "$s = Get-AuthenticodeSignature -LiteralPath $env:FF_SIG_PATH; "
            "$c = $s.SignerCertificate; "
            "[pscustomobject]@{ Status = [string]$s.Status; StatusMessage = $s.StatusMessage; "
            "SignatureType = [string]$s.SignatureType; "
            "Subject = $c.Subject; Issuer = $c.Issuer; SerialNumber = $c.SerialNumber; "
            "Thumbprint = $c.Thumbprint; "
            "NotBefore = if ($c) { $c.NotBefore.ToString('yyyy-MM-dd HH:mm:ss') } else { $null }; "
            "NotAfter = if ($c) { $c.NotAfter.ToString('yyyy-MM-dd HH:mm:ss') } else { $null } "
            "} | ConvertTo-Json -Compress"
        )
        env = dict(os.environ, FF_SIG_PATH=str(file_path))
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            status = data.get("Status") or ""

            is_signed = status not in (
                "NotSigned",
                "UnknownError",
                "NotSupportedFileFormat",
                "",
            )
            is_valid = status == "Valid"

            return SignatureInfo(
                is_signed=is_signed,
                is_valid=is_valid,
                signer_name=data.get("Subject"),
                issuer_name=data.get("Issuer"),
                serial_number=data.get("SerialNumber"),
                thumbprint=data.get("Thumbprint"),
                valid_from=data.get("NotBefore"),
                valid_to=data.get("NotAfter"),
                signature_type=f"Authenticode ({data.get('SignatureType') or 'Embedded'})",
                error_message=None
                if is_valid or not is_signed
                else data.get("StatusMessage"),
            )

    except (
        subprocess.SubprocessError,
        json.JSONDecodeError,
        KeyError,
        OSError,
        AttributeError,
    ):
        pass

    # Fallback: try sigcheck.exe if available
    try:
        # Look for sigcheck in common locations
        sigcheck_paths = [
            "C:\\Sysinternals\\sigcheck.exe",
            "C:\\SysinternalsSuite\\sigcheck.exe",
            os.path.join(
                os.environ.get("ProgramFiles", ""), "Sysinternals", "sigcheck.exe"
            ),
            shutil.which("sigcheck.exe") or shutil.which("sigcheck64.exe") or "",
        ]

        sigcheck_exe = None
        for path in sigcheck_paths:
            if path and os.path.exists(path):
                sigcheck_exe = path
                break

        if sigcheck_exe:
            result = subprocess.run(
                [sigcheck_exe, "-accepteula", file_path],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                lines = result.stdout.split("\n")
                for line in lines:
                    if "Verified:" in line:
                        is_signed = "Signed" in line
                        is_valid = "OK" in line or "Valid" in line
                        return SignatureInfo(
                            is_signed=is_signed,
                            is_valid=is_valid,
                            signature_type="Authenticode",
                        )

    except (subprocess.SubprocessError, OSError):
        pass

    return SignatureInfo(is_signed=False, error_message="Could not inspect signature")


def inspect_signature_macos(file_path: str) -> SignatureInfo:
    """Inspect an Apple code signature using the built-in `codesign` tool."""
    if not shutil.which("codesign"):
        return SignatureInfo(is_signed=False, error_message="codesign tool not found")
    try:
        info = subprocess.run(
            ["codesign", "-dvv", "--", file_path],
            capture_output=True,
            text=True,
            timeout=15,
        )
        output = info.stderr or info.stdout
        if "not signed" in output or info.returncode != 0:
            return SignatureInfo(is_signed=False, signature_type="Apple code signature")

        authorities = re.findall(r"^Authority=(.+)$", output, re.MULTILINE)
        team = re.search(r"^TeamIdentifier=(.+)$", output, re.MULTILINE)
        signed_time = re.search(
            r"^(?:Signed Time|Timestamp)=(.+)$", output, re.MULTILINE
        )

        verify = subprocess.run(
            ["codesign", "--verify", "--deep", "--strict", "--", file_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        is_valid = verify.returncode == 0
        return SignatureInfo(
            is_signed=True,
            is_valid=is_valid,
            signer_name=authorities[0]
            if authorities
            else ("Ad-hoc" if "adhoc" in output else None),
            issuer_name=" → ".join(authorities[1:]) or None,
            serial_number=team.group(1) if team else None,
            valid_from=signed_time.group(1) if signed_time else None,
            signature_type="Apple code signature",
            error_message=None
            if is_valid
            else (verify.stderr.strip() or "Verification failed"),
        )
    except (subprocess.SubprocessError, OSError) as e:
        return SignatureInfo(is_signed=False, error_message=str(e))


def inspect_signature(file_path: str) -> SignatureInfo:
    """
    Inspect digital signature of a file.
    Currently supports Authenticode on Windows.
    """
    if not os.path.exists(file_path):
        return SignatureInfo(is_signed=False, error_message="File does not exist")

    system = platform.system()
    if system == "Windows":
        return inspect_signature_windows(file_path)
    if system == "Darwin":
        return inspect_signature_macos(file_path)
    return SignatureInfo(
        is_signed=False,
        error_message="Embedded code signatures are only inspected on Windows and macOS",
    )


def check_pgp_signature(
    file_path: str, sig_file_path: Optional[str] = None
) -> SignatureInfo:
    """
    Check for PGP/GPG signature.
    """
    if not sig_file_path:
        # Detached signatures are conventionally "<file>.sig" (e.g. foo.tar.gz.sig);
        # also accept "<stem>.sig" for tools that replace the extension.
        base_path = os.path.splitext(file_path)[0]
        candidates = [file_path + ext for ext in (".sig", ".asc", ".gpg")]
        candidates += [base_path + ext for ext in (".sig", ".asc", ".gpg")]
        for potential_sig in candidates:
            if potential_sig != file_path and os.path.exists(potential_sig):
                sig_file_path = potential_sig
                break

    if not sig_file_path or not os.path.exists(sig_file_path):
        return SignatureInfo(is_signed=False, error_message="No signature file found")

    try:
        # Try to verify with GPG
        gpg = shutil.which("gpg") or shutil.which("gpg2")
        if not gpg:
            return SignatureInfo(
                is_signed=True,
                is_valid=False,
                signature_type="PGP/GPG",
                error_message=f"Signature file found ({os.path.basename(sig_file_path)}) but GPG is not installed",
            )
        result = subprocess.run(
            [gpg, "--batch", "--verify", sig_file_path, file_path],
            capture_output=True,
            text=True,
            timeout=30,
        )

        is_valid = result.returncode == 0

        # Extract signer info from output
        signer_name = None
        if result.stderr:
            lines = result.stderr.split("\n")
            for line in lines:
                if "Good signature from" in line:
                    # Extract name from "Good signature from "Name" <email>"
                    match = re.search(r'Good signature from "([^"]*)"', line)
                    if match:
                        signer_name = match.group(1)
                    break

        return SignatureInfo(
            is_signed=True,
            is_valid=is_valid,
            signer_name=signer_name,
            signature_type="PGP/GPG",
            error_message=result.stderr if not is_valid else None,
        )

    except (subprocess.SubprocessError, OSError):
        return SignatureInfo(
            is_signed=False,
            error_message="GPG not available or signature verification failed",
        )
