# Resumes

Approved resume source files belong in this directory. The current editable
resume source and its original archive are now stored here.

Current source:

- `Jeremy_Liu_Resume.tex` - editable LaTeX source added to the project on
  2026-09-10
- `Jeremy_Liu_Resume_source.zip` - original archive supplied with the source

Older Drive resumes were reviewed for corroboration but contain conflicting
contact details, dates, project lists, or GPA claims. The current source can be
registered directly:

```powershell
.\.venv\Scripts\job-agent.exe resume add swe-current "Current SWE resume" candidate/resumes/Jeremy_Liu_Resume.tex --base-type software-engineering --version 2026-09-10
```

The machine does not have a LaTeX compiler installed, so the source was not
rendered to PDF here. Compile it locally when a PDF upload is required.
