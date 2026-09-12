# Quality, Grounding, and Anti-Slop System

## Objective

The system must be able to answer:

> **Why should I trust that this application is not AI slop?**

The answer should come from measurable controls, not vibes.

---

## 1. Provenance requirement

Every factual candidate claim in generated text must map to a source.

Sources include:

- structured candidate fact;
- approved project;
- approved experience;
- approved story;
- approved prior answer.

Example:

```json
{
  "answer": "I led product direction for a multiplayer game...",
  "claims": [
    {
      "text": "led product direction",
      "source_id": "story.paper_cuts_leadership"
    }
  ],
  "unsupported_claims": []
}
```

If `unsupported_claims` is non-empty:

```text
FAIL
```

The answer cannot be automatically submitted.

---

## 2. Grounding gate

Pipeline:

```text
generated answer
 ↓
claim extraction
 ↓
candidate-source matching
 ↓
unsupported claim check
 ↓
PASS / FAIL
```

The grounding checker may remove unsupported content.

It may not invent evidence to justify it.

---

## 3. Style gate

Maintain:

```text
candidate/style.md
```

with:

- preferred tone;
- disliked phrases;
- sentence patterns;
- approved examples;
- rejected examples;
- user edits.

Also retrieve several relevant approved answers before generating a new answer.

Do not merely prompt:

```text
"sound human"
```

Use actual user-approved writing as reference.

---

## 4. Slop critic

A separate critic should flag:

- generic enthusiasm;
- restating the company's homepage;
- empty adjectives;
- excessive corporate language;
- repeated JD wording;
- cliché openings;
- claims that could apply to any company;
- unnecessary verbosity;
- suspiciously polished phrasing inconsistent with user style.

Examples of likely flags:

```text
I am thrilled to apply...
I am incredibly passionate about...
Your innovative and cutting-edge mission...
I believe my diverse skill set aligns perfectly...
I leveraged...
```

These are examples, not an absolute blacklist.

---

## 5. Company-specific answer test

For questions such as:

> Why do you want to work here?

Require the answer plan to contain:

```text
specific company fact
+
specific candidate fact
+
actual connection between them
```

If the company name could be swapped with ten competitors without changing the answer, fail the answer.

---

## 6. Human edit learning

For every reviewed answer store:

```text
generated
final submitted
diff
question category
company
job
```

Track:

```text
untouched rate
minor-edit rate
major-rewrite rate
median normalized edit distance
unsupported-claim count
critic rejection rate
```

Example target before increasing autonomy:

```text
unsupported factual claims: 0
major rewrite rate: <5%
median edit distance: low
```

Do not choose final thresholds until real data exists.

---

## 7. Submission risk classes

### GREEN

Safe to fill automatically:

- legal name;
- known contact information;
- known school/degree;
- known links;
- resume upload;
- previously approved factual yes/no answers.

### YELLOW

Generate but evaluate carefully:

- new free-response question;
- new company-specific answer;
- interpretation-dependent question;
- novel story composition.

### RED

Require human answer unless explicit stored policy exists:

- unknown facts;
- work authorization ambiguity;
- demographic/EEO;
- legal attestations;
- salary decisions;
- relocation decisions not represented in structured facts;
- anything with low grounding confidence.

---

## 8. Resume quality

Do not ask an LLM to freely rewrite the resume.

Represent resume content as approved source bullets.

The model may:

- select bullets;
- reorder;
- shorten;
- adapt terminology;
- emphasize evidence.

It may not:

- invent scale;
- invent impact;
- add technologies never used;
- turn participation into leadership;
- invent metrics.

Suggested flow:

```text
JD rubric
 ↓
candidate evidence matrix
 ↓
select base resume
 ↓
select verified bullets
 ↓
limited rewrite
 ↓
claim comparison against sources
 ↓
ATS readability check
 ↓
render
```

---

## 9. Tier A policy

Tier A applications are intentionally human-led.

The system should still prepare:

- JD summary;
- likely screening rubric;
- strengths/gaps;
- resume recommendation;
- answer ideas;
- company-specific research;
- possible referral/network paths.

But the user performs the meaningful application work.

Manual Tier A applications are valuable training examples for future Tier B/C quality.

---

## 10. Autonomy should be earned

Initial policy:

```text
agent fills + prepares
human submits
```

Later, auto-submit can be enabled only for application categories with demonstrated reliability.

Use historical data, not confidence theater.

The product should be able to explain:

```text
Why did this answer pass?
What candidate sources support it?
How often does the user rewrite this type of answer?
Why was this application allowed to submit automatically?
```
