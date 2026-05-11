# Local Dependencies

Put offline installers or wheels in this folder when distributing the project to a new PC.

Supported files:

- `python-*.exe`: optional bundled Python installer. The installer script will use it before trying `winget`.
- `PySide6*.whl`
- `PySide6_Addons*.whl`
- `PySide6_Essentials*.whl`
- `shiboken6*.whl`

Example download command on a networked PC:

```powershell
python -m pip download PySide6 -d .\dependencies
```

After these files are present, `install_and_run.bat` installs PySide6 with:

```text
pip install --no-index --find-links .\dependencies PySide6
```
