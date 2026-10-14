> **File use case:** Defines the existing data-explanation and Home enhancement.
> **What it does:** Records context inputs, qualitative interpretation limits and presentation contracts.

# Meaning-first reading

An orientation request such as “Help me understand this data” now uses the
configured primary model when model access is enabled. It receives current field
names/types, saved definitions, the actor's private goal and up to three checked
reading-note passages for this upload. It receives neither raw rows nor calculated
values in this path. General documents still use explicit authorized retrieval;
this path does not search the web or every workspace document.

The model proposes a short purpose statement, conceptual field groupings and at
most two existing measure/category exploration choices. The response must use
known fields, bounded plain text and the exact schema. Numeric prose, markup,
links and unknown fields are rejected. These structural checks do not prove that
every qualitative interpretation is correct. The interface calls it an AI
interpretation and distinguishes possible questions from measured findings.
Confirmed meanings outrank notes and guesses. No model arithmetic, causal claims,
new domain thresholds, implicit units or automatic definition changes are authorized.

The server converts eligible choices into questions, respects declared metric
calculations and defaults to an average when no calculation was declared. A
missing meaning or unit suppresses that calculation suggestion and produces one
focused question with the existing Complete missing details action. Confirmed
row meaning is reused. No-date files retain an explicit time-forecast limitation.
The existing review saves explicit answers; conversational prose is not silently
promoted to a shared definition or unit.

One bounded primary-model call is added to this explanation path. Unavailable,
timed-out or invalid output falls back to saved file information with a visible
notice. Notes are reauthorized and checked before and after the model call; current
source identity and private goal are also rechecked. Concurrent changes require
a fresh request. Results remain private immutable conversation turns, retain their
model route and source versions, and receive no calculated-result badge.

Recognized headings render as semantic cards; context details use a keyboard
accessible disclosure. Historical plain explanations remain readable and source
text is rendered as text. Home shows the saved purpose, definition state and the
current user's private goal, with existing explain/explore/review actions. Source
changes clear stale context; unsuccessful loading does not invent a description.

This improves existing guidance and presentation. It does not add a statistical
method, train a prediction model, make every tool autonomous or establish full
ThoughtSpot parity. Public reference evidence is in
[the reference audit](meaning-first-reference-audit.md). Schema remains 0017,
feature counts remain 37 Done / 16 Partial / 11 Not yet, and production gates remain
unchanged. Verification is recorded separately after checks and deployment.
