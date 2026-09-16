# Repository links in the public UI

Priority: P3  
Owner: Codex

## Problem

Visitors cannot easily find OpenIQ's source repository from the login page or
the primary application interface.

## Scope

- Add an accessible link to the canonical OpenIQ Git repository on the login
  page.
- Add the same link to the main authenticated application interface.
- Open the external repository safely without disrupting the current OpenIQ
  session.

## Non-goals

- Changing authentication, navigation structure, or repository hosting.
- Adding third-party analytics or external assets.

## Dependencies

- The canonical repository URL remains `https://github.com/nztom/openiq`.

## Acceptance criteria

- Both pages visibly expose a keyboard-accessible Git repository link.
- The link has clear accessible text and opens the canonical repository in a
  new tab with safe external-link attributes.
- Existing page layout and login behaviour remain intact.

## Validation

- Add focused UI/browser coverage for the public login and authenticated main
  interface.
- Run the relevant test suite on Linux and Windows.
