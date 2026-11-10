"""Process-local audio policy for private Wine tests and null-sink capture."""
import os
import re


_DRIVERS = ('winepulse.drv', 'winealsa.drv', 'wineoss.drv', 'winepipewire.drv')


def audio_environment(environment, *, capture_sink=None):
    """Preserve loader overrides while preventing direct hardware fallback.

    A failed Pulse connection is not a mute: Wine can select ALSA instead.
    Disable all audio drivers for silent tests, or allow only builtin Pulse
    for an explicitly selected capture sink. Never write prefix/global state.
    The capture owner must verify that its named null sink exists first.
    """
    env = dict(environment)
    overrides = []
    for entry in env.get('WINEDLLOVERRIDES', '').split(';'):
        if not entry.strip():
            continue
        names, separator, mode = entry.partition('=')
        if not separator:
            raise ValueError('Malformed Wine DLL override')
        kept = [name.strip() for name in names.split(',')
                if name.strip().lower().lstrip('*') not in _DRIVERS]
        if kept:
            overrides.append(','.join(kept) + '=' + mode)
    blocked = list(_DRIVERS)
    if capture_sink is not None:
        if not re.fullmatch(r'moonlab_slime_[0-9a-f]{12}', capture_sink):
            raise ValueError('Audio capture requires an owned Moon Sweepers null sink')
        blocked.remove('winepulse.drv')
        overrides.append('winepulse.drv=b')
        env.update(PULSE_SERVER=f'unix:/run/user/{os.getuid()}/pulse/native',
                   PULSE_SINK=capture_sink, ALSOFT_DRIVERS='pulse', SDL_AUDIODRIVER='pulseaudio')
    else:
        # Clear inherited routing as well as replacing older fake-server values.
        env.update(PULSE_SERVER='', PULSE_SINK='', ALSOFT_DRIVERS='null', SDL_AUDIODRIVER='dummy')
    overrides.append(','.join(blocked) + '=')
    env['WINEDLLOVERRIDES'] = ';'.join(overrides)
    return env
