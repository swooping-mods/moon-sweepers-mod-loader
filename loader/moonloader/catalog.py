"""Optional catalog metadata and shared filtering for every library view."""
import re

CATEGORIES = {'framework': 'Framework', 'qol': 'QoL', 'additions': 'Additions'}
MAX_TAGS = 24
TAG = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')


def metadata(config):
    """Validate presentation fields when publishing our catalog metadata.

    These optional manifest fields do not change the SDK/runtime contract.
    Older packages remain valid and visible in All mods and Enabled.
    """
    fields = {}
    if 'category' in config:
        value = config['category']
        if not isinstance(value, str) or value not in CATEGORIES:
            raise ValueError('Unknown mod category')
        fields['category'] = value
    if 'tags' in config:
        values = config['tags']
        if (not isinstance(values, list) or len(values) > MAX_TAGS or
                any(not isinstance(v, str) or len(v) > 48 or not TAG.fullmatch(v) for v in values) or
                len(values) != len(set(values))):
            raise ValueError('Invalid mod tags')
        fields['tags'] = list(values)
    return fields


def category(mod):
    value = mod.get('category', '')
    return value if isinstance(value, str) and value in CATEGORIES else ''


def tags(mod):
    # Imported legacy packages may carry unknown extension data. Ignore invalid
    # presentation fields without making the package itself unusable.
    try:
        return metadata({'tags': mod.get('tags', [])}).get('tags', [])
    except ValueError:
        return []


def description(mod):
    lines = []
    if category(mod):
        lines.append('Category: ' + CATEGORIES[category(mod)])
    if tags(mod):
        lines.append('Tags: ' + ', '.join(tags(mod)))
    return '\n'.join(lines)


def matches(mod, query='', mode='all', enabled=False):
    if mode == 'enabled' and not enabled:
        return False
    if mode in CATEGORIES and category(mod) != mode:
        return False
    # Match all query words across the name, description, category and tags.
    # Punctuation normalization makes co-op, co op and #co-op equivalent.
    fields = [mod.get(key, '') for key in ('id', 'name', 'summary', 'description')]
    fields.extend([category(mod), CATEGORIES.get(category(mod), ''), *tags(mod)])
    text = ' '.join(re.findall(r'\w+', ' '.join(fields).casefold()))
    return all(word in text for word in re.findall(r'\w+', query.casefold()))
