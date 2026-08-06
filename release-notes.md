# v0.0.24

New-project validation fix.

- The New Project wizard now requires an existing local Dropbox project folder
  before Preview is available.
- Empty, missing, and non-directory folder paths show precise inline errors;
  the plan validator enforces the same contract before launching `btwr new`.
- Folder paths entered by typing or paste update the derived project number,
  short name, repository name, production URL, and `04_Web` path immediately.
- Step headers no longer bypass the required Project info validation.
