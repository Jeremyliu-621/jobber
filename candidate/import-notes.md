---
id: import.google-drive-2026-09-10
type: import-notes
title: Google Drive candidate material review
topics: [provenance, review, conflicts]
approved: false
source: google-drive-review
---

# Google Drive review — 2026-09-10

## Imported as approved evidence

The structured profile and approved Markdown sources now use the local
`candidate/resumes/Jeremy_Liu_Resume.tex` source supplied on 2026-09-10:

- preferred name, email, phone, public links, and University of Toronto
  Computer Engineering education dates;
- Futurify, Chatforce, MannLab, and Robotics for Space Exploration experience;
- Paper Cuts, Ensemble, Aucctopus, and Straw projects;
- technical skills listed in the current resume.

The original archive is preserved as
`candidate/resumes/Jeremy_Liu_Resume_source.zip`.

## Deliberately unresolved

- Legal name is unset because the resume’s displayed name is not treated as a
  legal identity declaration.
- GPA is unset because reviewed resumes conflict between 3.04 and 3.42.
- Canada/US work authorization and sponsorship requirements remain unknown.
- Target roles, locations, remote preference, target companies, referrals, and
  excitement preferences were not explicitly supplied.
- “Present” roles are current only as of the 2026-09-10 source and should be
  rechecked before an application is prepared.

## Pending review

Older application documents contain potentially useful tutoring, Model UN,
Brazilian Jiu-Jitsu, DC motor teamwork, and hackathon stories. They are stored
under `candidate/stories/` or `candidate/answers/` with `approved: false` so
they can be reviewed without becoming application evidence.

Older resumes also contain conflicting contact details, dates, education
claims, and project histories. The older Stealth Startup record is retained as
unapproved pending confirmation; older project records remain separately
identified by their older Drive provenance.

The private life-story material in the `about me` document was used only for
writing-style signals. Its personal details were not copied into the candidate
brain.

## Resume file handling

The editable source is local, but it is not a rendered PDF. The application
planner only selects registered local resume records. Register the source with
the command in `candidate/resumes/README.md`; compile it to PDF separately when
an employer portal requires a PDF upload.
