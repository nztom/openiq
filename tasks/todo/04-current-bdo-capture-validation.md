# Current BDO capture and import validation

Priority: P2  
Owner: unassigned

## Problem

The packet decoder and OCR/import flows are validated only with historical or
synthetic data.

## Scope

- Obtain authorised, current-patch calibration and representative regional
  roster/score screenshots.
- Validate packet capture, long-running reconnect/deduplication, OCR review,
  and import correction against real-but-sanitised samples.
- Decide whether unsupported capture should remain experimental or be disabled
  in production-facing setup.

## Acceptance criteria

- Supported patch/region and calibration provenance are documented.
- Real sample results have an officer review record and regression fixtures where
  redistribution is permitted.
- Unsupported combinations fail safely and are clearly labelled.

## Validation

Run the packet/import verification suite plus a controlled real-session test.

