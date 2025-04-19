# 0.3.0
 - Added `Save` and `Reset` buttons to each preset line when the preset value has changed.
   - `Save` will open up a prompt to enter a name for the new preset, defaulting to the existing preset name
   - `Reset` will reset back to the currently selected preset's value.

## Known Issues
 - No confirmation prompt when overwriting existing custom preset
 - When saving a custom preset with the same name as a default preset, it will temporarily overwrite
   that default preset in the current dialog. This gets corrected upon the next instance of the dialog.

# 0.2.0
 - Remove dependency on openai python package since it has a dependency that requires platform-specific code. This is replaced with utilizing openai's REST API via urllib.
 - Fix fetching of previous stories. They were stored correctly, but not fetched correctly, which went unnoticed since some previous stories had still been stored under the collection path, masking the issue.

# 0.1.0
Initial release
