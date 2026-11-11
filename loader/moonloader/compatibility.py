"""Player reports and launch admission share the SDK's compatibility evaluator."""
import hashlib
import json
from . import discovery, game_profiles
from .storage import load

LABELS = {'verified': 'Verified for this exact setup',
          'requirements-matched': 'Requirements matched · gameplay not verified',
          'unknown': 'Unknown game build', 'incompatible': 'Incompatible'}


def reason(code, message, **values):
    return {'code': code, 'message': message, **values}


def receipt_digest(receipt):
    return hashlib.sha256(json.dumps(receipt, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def _blocked(result, item):
    result['allowed'] = False
    if item['code'] != 'unknown-game-profile' or result['status'] != 'incompatible':
        result['status'] = 'unknown' if item['code'] == 'unknown-game-profile' else 'incompatible'
    result.setdefault('reasons', []).append(item)


def runtime_adapter(receipt, profile):
    """Old receipts can only preserve their exact legacy game target."""
    explicit = receipt.get('game_adapter')
    if explicit is not None: return explicit
    if (profile and profile['id'] == game_profiles.CURRENT_PROFILE_ID
            and receipt.get('game_pins') == profile['hashes']):
        # This grants no game API or v8 ABI. It keeps the existing <=v7 path.
        return {'abi': 1, 'profiles': {profile['id']: {'digest': profile['digest'], 'capabilities': {}}}}
    return None


def report(service, installation, selected=None, *, library=None, inspection=None):
    from moon_mod_api.compatibility import evaluate
    chosen = list(service.state['selected'] if selected is None else selected)
    if library is None: library, errors = service.library()
    else: errors = {}
    manifests = {name: pair[0] for name, pair in library.items()}
    inspection_error = None
    try: target = inspection if inspection is not None else service.inspect(installation)
    except (ValueError, OSError) as error:
        target = {'compatible': False, 'hashes': {}, 'profile': None, 'reason': str(error)}
        inspection_error = reason('game-inspection-failed', str(error))
    profile = target.get('profile')
    receipt = load(service.bundle / 'runtime/receipt.json', {})
    metadata_error = not isinstance(receipt, dict)
    if metadata_error: receipt = {}
    native_abis = receipt.get('native_package_abis')
    if native_abis is not None:
        if not isinstance(native_abis, list): metadata_error = True; native_abis = []
        else: native_abis = [f'MoonLab_ModStart/v{n}' if type(n) is int else n for n in native_abis]
    context = {'game_profile': profile, 'game_adapter': runtime_adapter(receipt, profile),
               'available_runtimes': service.available_runtimes(installation),
               'runtime_api_abi': receipt.get('runtime_api_abi', 0),
               'runtime_readiness_abi': receipt.get('runtime_readiness_abi', 0),
               'host_capabilities': receipt.get('host_capabilities') or {},
               'native_package_abis': native_abis, 'runtime_sha256': receipt.get('sha256'),
               'legacy_profile_ids': {'native': [game_profiles.CURRENT_PROFILE_ID],
                                      'bepinex-il2cpp': [game_profiles.CURRENT_PROFILE_ID]}}
    if not chosen and service.mode(installation) == 'installed':
        result = {'status': 'requirements-matched', 'allowed': True, 'mods': {}, 'reasons': [],
                  'profile': {'id': profile['id'], 'digest': profile['digest']} if profile else None,
                  'order': [], 'selection_digest': None}
    else:
        result = evaluate(manifests, chosen, target.get('hashes', {}), **context)
    result['schema'] = 'moon-loader-compatibility/v1'
    result['game'] = {'description': target.get('reason', ''), 'hashes': target.get('hashes', {}),
                      'known': bool(profile), 'version': profile.get('version') if profile else None,
                      'backend': profile.get('backend') if profile else None,
                      'architecture': profile.get('architecture') if profile else None}
    result['selected'] = chosen
    result['runtime_receipt_digest'] = receipt_digest(receipt)
    result['qualification'] = 'Requirements matching does not verify gameplay, saves, performance or co-op.'
    if metadata_error: _blocked(result, reason('runtime-metadata', 'Loader runtime metadata is invalid; reinstall the loader.'))
    if inspection_error: _blocked(result, inspection_error)
    elif not profile and not any(r['code'] == 'game-build-unknown' for r in result.get('reasons', [])):
        _blocked(result, reason('unknown-game-profile', target.get('reason', 'Unrecognized game build')))
    if profile:
        adapter = receipt.get('game_adapter')
        if adapter is not None:
            profiles = adapter.get('profiles') if isinstance(adapter, dict) else None
            supported = profiles.get(profile['id']) if isinstance(profiles, dict) and type(adapter.get('abi')) is int and adapter['abi'] == 1 else None
            admitted = (isinstance(supported, dict) and supported.get('digest') == profile['digest']
                        and receipt_digest(supported.get('capabilities')) == receipt_digest(profile['capabilities']))
        else:
            admitted = runtime_adapter(receipt, profile) is not None
        if not admitted:
            _blocked(result, reason('runtime-profile-unavailable',
                                    'This loader runtime does not support the exact reviewed game profile. Update the loader adapter.'))
    from .storage import sha
    runtime = service.bundle / 'runtime/windows-x64/version.dll'
    if not runtime.is_file() or sha(runtime) != receipt.get('sha256'):
        _blocked(result, reason('runtime-integrity', 'Loader runtime is missing or changed; rebuild or reinstall the loader.'))
    for name in chosen:
        if name in errors:
            item = reason('package-integrity', errors[name], mod=name)
            _blocked(result, item)
            result.setdefault('mods', {}).setdefault(name, {'status': 'incompatible', 'reasons': [], 'requirements': []})['reasons'].append(item)
    return result


def message(result):
    messages = [item['message'] for item in result.get('reasons', [])]
    messages.extend(why['message'] for item in result.get('mods', {}).values() for why in item.get('reasons', []))
    return '; '.join(dict.fromkeys(messages)) or LABELS.get(result['status'], result['status'])


def describe(result, names=None):
    names = names or {}
    lines = [LABELS.get(result['status'], result['status']), '',
             'Game: ' + result.get('game', {}).get('description', 'Not inspected'),
             result.get('qualification', ''), '']
    if result.get('selected') == []: lines.append('No mods selected. Installed preparation leaves mod startup disabled.')
    lines.extend('• ' + item['message'] for item in result.get('reasons', []))
    for name, item in result.get('mods', {}).items():
        lines += ['', names.get(name, name) + ': ' + LABELS.get(item['status'], item['status'])]
        lines.extend('  ' + why['message'] for why in item.get('reasons', []))
        for need in item.get('requirements', []):
            # SDK reports are machine-readable; keep raw addresses/digests out
            # of the ordinary player explanation.
            if isinstance(need, dict):
                if need.get('kind') == 'native-package-abi':
                    lines.append('  ' + str(need.get('required', 'Native package ABI')) +
                                 (' · available' if need.get('available') else ' · runtime support missing'))
                    continue
                title = need.get('name', need.get('api', need.get('capability', need.get('id', 'Requirement'))))
                state = 'optional' if need.get('optional') else 'required'
                provider = need.get('provider')
                if isinstance(provider, dict): provider = provider.get('name', provider.get('id'))
                actual = need.get('actual')
                required = 'ABI ' + str(need.get('required_abi', '?')) + ', table ≥ ' + str(need.get('required_min_size', '?'))
                offered = ('found ABI ' + str(actual.get('abi')) + ', table ' + str(actual.get('size'))
                           if isinstance(actual, dict) else 'not available' + ('; optional integration skipped' if need.get('optional') else ''))
                lines.append('  ' + str(title) + ' · ' + state + ' · ' + required + ' · ' + offered
                             + (' · ' + str(provider) if provider else ''))
    return '\n'.join(lines).strip()
