"""Presentation state; a Steam request never establishes game lifetime."""
from dataclasses import dataclass


@dataclass
class LaunchFeedback:
    phase: str = 'idle'
    installed: bool = True
    observed_running: bool = False
    request_code: int | None = None

    @property
    def blocked(self):
        return self.phase not in ('idle', 'closed')

    def requested(self, installed=True):
        self.installed = installed
        self.phase = 'waiting'
        self.request_code = None
        self.observed_running = False

    def request_finished(self, code):
        self.request_code = code
        # Even a failed request can have reached Steam. Keep the guard until
        # observed exit or acknowledgement, without labelling it a game crash.
        if not self.observed_running:
            self.phase = 'failed' if code else 'unconfirmed'

    def observe(self, status):
        if status == 'running':
            self.observed_running = True
            self.phase = 'running'
        elif status == 'absent' and self.observed_running:
            self.phase = 'closed'
        elif status == 'unavailable' and self.observed_running:
            self.phase = 'unconfirmed'

    @property
    def message(self):
        if not self.installed:
            if self.phase == 'waiting': return 'Private launch process is active; game startup is unconfirmed. Close the game normally when finished.'
            if self.phase == 'unconfirmed': return 'Private launch process finished; game lifetime is unconfirmed. If the game closed or did not start, use “Game closed / did not start…”.'
            if self.phase == 'failed': return 'The private launch process failed. See launch diagnostics; confirm the game closed before another launch.'
        return {
            'waiting': 'Launch handed to Steam. Waiting for Moon Sweepers to appear; first managed startup can take longer.',
            'unconfirmed': 'Game startup or lifetime is unconfirmed. Check Steam and the game. If it closed or did not start, use “Game closed / did not start…”.',
            'running': 'Moon Sweepers is running. Mod startup is not confirmed by process detection. Close the game normally before another launch.',
            'finishing': 'Moon Sweepers is no longer observed. Waiting for the launch request or runner to finish before another launch.',
            'closed': 'Moon Sweepers closed. You can change mods or launch again.',
            'failed': 'Steam could not complete the launch request. Check Steam and launch diagnostics. If no game is running, use “Game closed / did not start…”.',
        }.get(self.phase, '')
