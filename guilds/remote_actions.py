"""Prepare slow external reads before acquiring the guild's write transaction."""
from .modules import ai, commands, integrations, operations
from .modules.core import Invalid, public, require, save, text, timestamp, now


def target(module, action, payload):
    if module == 'commands' and action == 'run':
        command = text(payload['command'], 'command', 80).lstrip('/')
        if command in commands.ALIASES:
            module, action = commands.ALIASES[command]
            return module, action, payload.get('arguments', {})
    return module, action, payload


def authorize(guild, module, action, payload, role):
    if module == 'commands' and action == 'run':
        command = text(payload['command'], 'command', 80).lstrip('/')
        require(role, commands.minimum_role(command))
        override = guild.config.get('command_permissions', {}).get(command)
        if override:
            require(role, override)


def prepare(guild, module, action, payload, role, user):
    """Return a local-only callback; the callback is never supplied by API input."""
    original_module = module
    module, action, payload = target(module, action, payload)
    if module == 'ai':
        result = ai.handle(guild, action, payload, role, user)
        return lambda current, current_role: result
    if module == 'integrations' and action in ('roster_fetch', 'roster_source', 'streams_refresh'):
        require(role, 'owner' if action == 'roster_source' else 'admin')
        if action == 'streams_refresh':
            data = integrations.fetch_streams(guild)
            return lambda current, current_role: public(save(current, 'streams', data, 'current'))
        url = text(payload['url'], 'guild page URL', 2000)
        names = integrations.fetch_roster(url)
        if action == 'roster_fetch':
            return lambda current, current_role: {'names': names, 'requires_confirmation': True}
        def source(current, current_role):
            current.config.setdefault('sync', {})['url'] = url
            current.save()
            return {'names': names, 'source_saved': True}
        return source
    if original_module == 'commands' and module == 'roster' and action == 'sync' and 'names' not in payload:
        require(role)
        url = guild.config.get('sync', {}).get('url')
        if not url:
            raise Invalid('Configure a verified roster source or provide reviewed names')
        prepared = {**payload, 'names': integrations.fetch_roster(url)}
        from .modules import roster
        return lambda current, current_role: roster.handle(current, 'sync', prepared, current_role, user)
    if module == 'operations' and action in ('tick', 'catchup'):
        require(role)
        prepared = {**payload, 'at': timestamp(payload.get('at', now()))}
        sources = {}
        for kind, key, day, at, config in operations.due_jobs(guild, action, prepared):
            url = config.get('url') if kind == 'sync' else None
            if url and url not in sources:
                try:
                    sources[url] = (integrations.fetch_roster(url), None)
                except Exception:
                    sources[url] = (None, 'Roster source unavailable; check configuration and retry')
        return lambda current, current_role: operations.handle(current, action, prepared, current_role, user, sources=sources)
    return None
