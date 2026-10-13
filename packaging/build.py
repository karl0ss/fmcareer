"""Build the single-file fmcareer executable with PyInstaller (run from the repo root).

    pip install ".[images,build]"
    python packaging/build.py

The result is dist/fmcareer.exe on Windows (dist/fmcareer on Linux and macOS).
The icon comes from fmcareer/web/logo.svg, rendered to packaging/icon.png and icon.ico.
"""

import sys

import PyInstaller.__main__

# Windows takes the .ico; macOS turns the .png into its own format; Linux executables carry no icon
ICON = {"win32": ["--icon", "packaging/icon.ico"], "darwin": ["--icon", "packaging/icon.png"]}.get(sys.platform, [])

PyInstaller.__main__.run(
    [
        "packaging/fmcareer_app.py",
        "--name",
        "fmcareer",
        "--onefile",
        "--console",  # the window shows where the app is running; closing it stops the app
        "--noconfirm",
        "--clean",
        *ICON,
        # fmsave's layout data, and the image readers with their native decoders
        "--collect-data",
        "fmcareer",  # the report's and the app's pages (fmcareer/web)
        "--collect-all",
        "fmsave",
        "--collect-all",
        "UnityPy",
        "--collect-all",
        "texture2ddecoder",
        "--collect-all",
        "etcpak",
        "--collect-all",
        "astc_encoder",
        "--collect-all",
        "archspec",
        "--collect-all",
        "fmod_toolkit",  # UnityPy loads its audio library on import
        "--copy-metadata",
        "fmsave",
        "--copy-metadata",
        "fmcareer",
        *sys.argv[1:],
    ]
)
