# Current BDO packet-capture validation

Priority: P2  
Owner: unassigned

## Problem

The packet decoder is validated only with historical or synthetic data.

## Scope

- Obtain authorised, current-patch calibration.
- Validate packet capture and long-running reconnect/deduplication against a
  controlled real session.
- Decide whether unsupported capture should remain experimental or be disabled
  in production-facing setup.

## Acceptance criteria

- Supported patch/region and calibration provenance are documented.
- Unsupported combinations fail safely and are clearly labelled.

## Validation

Run packet verification plus a controlled real-session test.
