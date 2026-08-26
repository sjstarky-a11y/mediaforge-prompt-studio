#!/usr/bin/env python3
"""Build deterministic Windows and Linux MediaForge release archives."""

from __future__ import annotations

import argparse
import binascii
import hashlib
import io
import json
import struct
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parent.parent
FIXED_ZIP_TIME = (2020, 1, 1, 0, 0, 0)
SYSTEM_DIRECTORY = PurePosixPath("MediaForge-System")
PACKAGE_MANIFEST = SYSTEM_DIRECTORY / "runtime/PACKAGE-MANIFEST.json"

COMMON_FILES = (
    Path(".dockerignore"),
    Path(".env.example"),
    Path("CHANGELOG.md"),
    Path("Dockerfile"),
    Path("LICENSE"),
    Path("PACKAGING-V0.3.md"),
    Path("README.md"),
    Path("SECURITY.md"),
    Path("docker-compose.nvidia.yml"),
    Path("docker-compose.yml"),
    Path("requirements.txt"),
)
COMMON_DIRECTORIES = (
    Path("app"),
    Path("image_cuda"),
    Path("image_flux"),
    Path("LICENSES"),
    Path("models"),
)
WINDOWS_FILES = (
    Path("MediaForge-Windows.cmd"),
    Path("START-HERE-WINDOWS.txt"),
    Path("detect-hardware.ps1"),
    Path("detect-runtime.ps1"),
    Path("install.ps1"),
    Path("manage-models.ps1"),
    Path("runtime-policy.ps1"),
    Path("start.ps1"),
    Path("status.ps1"),
    Path("stop.ps1"),
)
LINUX_FILES = (
    Path("MediaForge-Linux.sh"),
    Path("START-HERE-LINUX.txt"),
    Path("detect-hardware.sh"),
    Path("detect-runtime.sh"),
    Path("doctor.sh"),
    Path("install.sh"),
    Path("manage-models.sh"),
    Path("runtime-policy.sh"),
    Path("scripts/linux_profile.py"),
    Path("scripts/mediaforge-common.sh"),
    Path("start.sh"),
    Path("status.sh"),
    Path("stop.sh"),
)
PRIVATE_PATH_NAMES = {
    ".env",
    ".git",
    "data",
    "hardware-profile.json",
    "runtime-profile.json",
    "install-log.txt",
    "install-linux.log",
    "doctor-report.txt",
}


@dataclass(frozen=True)
class PlatformSpec:
    key: str
    folder_suffix: str
    archive_suffix: str
    files: tuple[Path, ...]


WINDOWS = PlatformSpec(
    key="windows",
    folder_suffix="Windows-x64",
    archive_suffix=".zip",
    files=WINDOWS_FILES,
)
LINUX = PlatformSpec(
    key="linux",
    folder_suffix="Linux-x86_64",
    archive_suffix=".tar.gz",
    files=LINUX_FILES,
)
PLATFORMS = (WINDOWS, LINUX)

USER_ROOT_FILES = {
    "windows": {
        PurePosixPath("LICENSE"),
        PurePosixPath("MediaForge-Windows.cmd"),
        PurePosixPath("README.md"),
        PurePosixPath("START-HERE-WINDOWS.txt"),
    },
    "linux": {
        PurePosixPath("LICENSE"),
        PurePosixPath("MediaForge-Linux.sh"),
        PurePosixPath("README.md"),
        PurePosixPath("START-HERE-LINUX.txt"),
    },
}


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_name(version: str, spec: PlatformSpec) -> str:
    clean_version = version.strip()
    if not clean_version or any(char in clean_version for char in "\\/\0"):
        raise ValueError("Version must be a non-empty filesystem-safe value.")
    return f"MediaForge-Prompt-Studio-{clean_version}-{spec.folder_suffix}"


def _directory_files(source_root: Path, relative_directory: Path) -> list[Path]:
    directory = source_root / relative_directory
    if not directory.is_dir():
        raise FileNotFoundError(f"Required directory is missing: {relative_directory}")
    result: list[Path] = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source_root)
        if "__pycache__" in relative.parts or path.suffix == ".pyc":
            continue
        result.append(relative)
    return result


def collect_source_files(source_root: Path, spec: PlatformSpec) -> tuple[Path, ...]:
    selected = set(COMMON_FILES)
    selected.update(spec.files)
    for directory in COMMON_DIRECTORIES:
        selected.update(_directory_files(source_root, directory))

    missing = [relative for relative in selected if not (source_root / relative).is_file()]
    if missing:
        rendered = ", ".join(path.as_posix() for path in sorted(missing))
        raise FileNotFoundError(f"Required release files are missing: {rendered}")

    for relative in selected:
        if any(part in PRIVATE_PATH_NAMES for part in relative.parts):
            raise ValueError(f"Private path selected for release: {relative.as_posix()}")
    return tuple(sorted(selected, key=lambda path: path.as_posix()))


def release_destination(relative: Path, spec: PlatformSpec) -> Path:
    """Map a source file to its intentionally simple release location."""
    posix_relative = PurePosixPath(relative.as_posix())
    if posix_relative in USER_ROOT_FILES[spec.key]:
        return relative
    return Path(SYSTEM_DIRECTORY.as_posix()) / relative


def _normalized_content(source: Path, relative: Path, spec: PlatformSpec) -> bytes:
    content = source.read_bytes()
    if spec.key == "windows" and relative.suffix.lower() in {".cmd", ".txt"}:
        text = content.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        return text.replace("\n", "\r\n").encode("utf-8")
    return content


def _release_info(version: str, spec: PlatformSpec) -> bytes:
    payload = {
        "application": "MediaForge Prompt Studio",
        "version": version,
        "platform": spec.key,
        "architecture": "x86_64",
        "runtime_selection": "automatic CPU or NVIDIA",
        "models_included": False,
    }
    return (json.dumps(payload, indent=2) + "\n").encode("utf-8")


def _manifest_entries(release_root: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for path in sorted(release_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(release_root)
        if PurePosixPath(relative.as_posix()) == PACKAGE_MANIFEST:
            continue
        content = path.read_bytes()
        entries.append(
            {
                "file": relative.as_posix(),
                "bytes": len(content),
                "sha256": sha256_bytes(content),
            }
        )
    return entries


def create_release_tree(
    source_root: Path,
    staging_parent: Path,
    version: str,
    spec: PlatformSpec,
) -> Path:
    release_root = staging_parent / package_name(version, spec)
    release_root.mkdir(parents=True, exist_ok=False)

    for relative in collect_source_files(source_root, spec):
        release_relative = release_destination(relative, spec)
        destination = release_root / release_relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(_normalized_content(source_root / relative, relative, spec))
        mode = 0o755 if spec.key == "linux" and release_relative.suffix == ".sh" else 0o644
        destination.chmod(mode)

    system_directory = release_root / Path(SYSTEM_DIRECTORY.as_posix())
    system_directory.mkdir(parents=True, exist_ok=True)
    (system_directory / "RELEASE-INFO.json").write_bytes(_release_info(version, spec))
    runtime_directory = system_directory / "runtime"
    runtime_directory.mkdir(parents=True, exist_ok=True)
    manifest = _manifest_entries(release_root)
    (runtime_directory / "PACKAGE-MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    verify_release_tree(release_root, spec)
    return release_root


def verify_release_tree(release_root: Path, spec: PlatformSpec) -> None:
    manifest_path = release_root / Path(PACKAGE_MANIFEST.as_posix())
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("Release package manifest is missing or invalid.") from exc

    expected = _manifest_entries(release_root)
    if manifest != expected:
        raise ValueError("Release package manifest does not match packaged files.")

    paths = {entry["file"] for entry in manifest}
    forbidden = [
        path
        for path in paths
        if any(part in PRIVATE_PATH_NAMES for part in PurePosixPath(str(path)).parts)
    ]
    if forbidden:
        raise ValueError(f"Private files found in release: {forbidden}")

    if spec.key == "windows":
        required = {
            "MediaForge-Windows.cmd",
            "START-HERE-WINDOWS.txt",
            "MediaForge-System/install.ps1",
        }
        prohibited_suffix = ".sh"
    else:
        required = {
            "MediaForge-Linux.sh",
            "START-HERE-LINUX.txt",
            "MediaForge-System/install.sh",
            "MediaForge-System/scripts/mediaforge-common.sh",
        }
        prohibited_suffix = ".ps1"
    missing = required - paths
    if missing:
        raise ValueError(f"Required {spec.key} files are missing: {sorted(missing)}")
    if any(str(path).endswith(prohibited_suffix) for path in paths):
        raise ValueError(f"Opposite-platform launcher found in {spec.key} package.")


def _zip_info(name: str, mode: int) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = (mode & 0xFFFF) << 16
    return info


def create_windows_zip(release_root: Path, output_path: Path) -> None:
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(release_root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(release_root.parent).as_posix()
            archive.writestr(_zip_info(relative, 0o644), path.read_bytes())


def _tar_info(name: str, size: int, mode: int, is_directory: bool = False) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.size = size
    info.mode = mode
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    if is_directory:
        info.type = tarfile.DIRTYPE
    return info


def _deterministic_gzip(content: bytes) -> bytes:
    """Return a gzip stream without platform- or zlib-dependent bytes."""
    output = bytearray(b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\xff")
    block_size = 65535
    offsets = range(0, len(content), block_size) if content else (0,)
    for offset in offsets:
        block = content[offset : offset + block_size]
        final = offset + len(block) >= len(content)
        output.append(0x01 if final else 0x00)
        output.extend(struct.pack("<H", len(block)))
        output.extend(struct.pack("<H", len(block) ^ 0xFFFF))
        output.extend(block)
    output.extend(
        struct.pack(
            "<II",
            binascii.crc32(content) & 0xFFFFFFFF,
            len(content) & 0xFFFFFFFF,
        )
    )
    return bytes(output)


def create_linux_tar(release_root: Path, output_path: Path) -> None:
    tar_output = io.BytesIO()
    with tarfile.open(fileobj=tar_output, mode="w", format=tarfile.GNU_FORMAT) as archive:
        root_name = release_root.name
        archive.addfile(_tar_info(root_name, 0, 0o755, is_directory=True))
        for path in sorted(release_root.rglob("*")):
            relative = path.relative_to(release_root).as_posix()
            archive_name = f"{root_name}/{relative}"
            if path.is_dir():
                archive.addfile(_tar_info(archive_name, 0, 0o755, is_directory=True))
                continue
            mode = 0o755 if path.suffix == ".sh" else 0o644
            content = path.read_bytes()
            archive.addfile(_tar_info(archive_name, len(content), mode), io.BytesIO(content))
    output_path.write_bytes(_deterministic_gzip(tar_output.getvalue()))


def _safe_member_path(name: str) -> bool:
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts


def verify_archive(archive_path: Path, spec: PlatformSpec) -> None:
    with tempfile.TemporaryDirectory(prefix="mediaforge-release-verify-") as temporary:
        extract_root = Path(temporary)
        if spec.key == "windows":
            with zipfile.ZipFile(archive_path) as archive:
                if not all(_safe_member_path(name) for name in archive.namelist()):
                    raise ValueError("Unsafe path detected in Windows release archive.")
                archive.extractall(extract_root)
        else:
            with tarfile.open(archive_path, "r:gz") as archive:
                members = archive.getmembers()
                if not all(_safe_member_path(member.name) for member in members):
                    raise ValueError("Unsafe path detected in Linux release archive.")
                install_member = next(
                    (
                        member
                        for member in members
                        if member.name.endswith("/MediaForge-System/install.sh")
                    ),
                    None,
                )
                if install_member is None or install_member.mode & 0o111 == 0:
                    raise ValueError("Linux install.sh is not executable in the archive.")
                launcher_member = next(
                    (member for member in members if member.name.endswith("/MediaForge-Linux.sh")),
                    None,
                )
                if launcher_member is None or launcher_member.mode & 0o111 == 0:
                    raise ValueError("MediaForge-Linux.sh is not executable in the archive.")
                archive.extractall(extract_root, filter="data")

        roots = [path for path in extract_root.iterdir() if path.is_dir()]
        if len(roots) != 1:
            raise ValueError("Release archive must contain exactly one root folder.")
        verify_release_tree(roots[0], spec)


def build_releases(source_root: Path, output_directory: Path, version: str) -> list[Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    artifacts: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="mediaforge-release-build-") as temporary:
        staging_parent = Path(temporary)
        for spec in PLATFORMS:
            release_root = create_release_tree(source_root, staging_parent, version, spec)
            artifact = output_directory / f"{release_root.name}{spec.archive_suffix}"
            if spec.key == "windows":
                create_windows_zip(release_root, artifact)
            else:
                create_linux_tar(release_root, artifact)
            verify_archive(artifact, spec)
            artifacts.append(artifact)

    checksums = output_directory / f"SHA256SUMS-{version}.txt"
    lines = [f"{sha256_file(path)}  {path.name}" for path in artifacts]
    checksums.write_text("\n".join(lines) + "\n", encoding="utf-8")
    artifacts.append(checksums)
    return artifacts


def check_reproducibility(source_root: Path, version: str) -> None:
    with tempfile.TemporaryDirectory(prefix="mediaforge-release-check-") as temporary:
        base = Path(temporary)
        first = build_releases(source_root, base / "first", version)
        second = build_releases(source_root, base / "second", version)
        first_map = {path.name: path.read_bytes() for path in first}
        second_map = {path.name: path.read_bytes() for path in second}
        if first_map != second_map:
            raise ValueError("Release archives are not reproducible.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="v0.3")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.check:
        check_reproducibility(ROOT, args.version)
        print("Windows and Linux release packaging validation passed.")
        return

    artifacts = build_releases(ROOT, args.output.resolve(), args.version)
    print("MediaForge release artifacts:")
    for artifact in artifacts:
        print(f"- {artifact} ({artifact.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
