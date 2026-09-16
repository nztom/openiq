# Compose and Swarm deployment examples

Priority: P1  
Owner: Codex

## Problem

Operators need version-controlled, credential-free examples for running OpenIQ
with ordinary Docker Compose or Docker Swarm, along with reproducible image
build and deployment instructions.

## Scope

- Add a normal Docker Compose example for a single-host installation.
- Add a Docker Swarm stack example using a locally persistent SQLite data
  volume, an optional network backup mount, and a reverse-proxy overlay
  network.
- Document image build, tag, registry push, configuration, secret creation,
  deployment, upgrade, and verification steps.
- Ensure examples use placeholders and templates only; no live hostnames,
  credentials, secret values, or private network paths.

## Non-goals

- Deploying a new production stack or changing an operator's existing Swarm
  configuration.
- Providing an automated cluster bootstrap or a general-purpose secret manager.

## Dependencies

- Task 06 (backup/restore container behaviour) supplies the backup environment
  contract used by these examples.

## Acceptance criteria

- A new operator can use the Compose example to build and run OpenIQ with
  persistent application data and an optional mounted backup directory.
- A Swarm operator can build/push an immutable image, create required secrets,
  deploy the stack with an external proxy network, and keep SQLite data local to
  the selected node while restoring verified snapshots after failover.
- Examples validate with their respective Docker Compose and Swarm parsers.
- Documentation explains TLS termination, the HTTP upstream port, and the
  distinction between environment configuration and Docker secrets.

## Validation

- Render both examples with Docker Compose configuration validation.
- Validate Swarm-stack parsing against a local or test Swarm manager.
- Review the documented shell commands on Linux and Windows-compatible Docker
  environments.

## Implementation status

- Added credential-free single-host Compose and Swarm stack examples, an
  ignored Compose environment-file destination, and deployment documentation
  covering image build/push, secrets, backup restore, proxy routing, and
  upgrade checks.
- `docker compose --env-file examples/compose.env.example -f
  examples/docker-compose.yaml config --quiet` and `docker stack config -c
  examples/swarm-compose.yaml` pass on Linux.
- The complete Django test suite passes on Linux. Windows command review and a
  test-Swarm-manager deployment remain required before closing this task.
- The documentation sweep aligned the upgrade procedure and historical
  readiness record with main-container backups and the `/backups` mount.
