# 0.2.0
 - Remove dependency on openai python package since it has a dependency that requires platform-specific code. This is replaced with utilizing openai's REST API via urllib.
 - Fix fetching of previous stories. They were stored correctly, but not fetched correctly, which went unnoticed since some previous stories had still been stored under the collection path, masking the issue.

# 0.1.0
Initial release
