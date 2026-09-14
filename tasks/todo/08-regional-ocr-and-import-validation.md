# Regional OCR and import validation

Priority: P2  
Owner: unassigned

## Problem

OCR, roster, and score-import flows have synthetic coverage but lack
representative current regional samples.

## Scope

- Obtain authorised, sanitised roster and score screenshots plus import samples.
- Validate OCR review/correction and roster/score import against those samples.
- Add redistributable regression fixtures only where permission allows.

## Acceptance criteria

- Supported regions and known limitations are documented.
- Officer-reviewed sample outcomes are recorded without committing guild-private
  data.
- Unsupported formats fail clearly and safely.

## Validation

Run the import and OCR verification suite and a controlled review of the real
samples.

