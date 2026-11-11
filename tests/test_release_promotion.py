"""Promotion must reject incomplete assets or evidence for another commit/tag."""
import copy
import hashlib
import unittest

from promote_release import validate_candidate


class PromotionChecks(unittest.TestCase):
    def candidate(self):
        tag = 'v0.2.0'
        names = ['moon-sweepers-mod-loader-0.2.0' + suffix for suffix in (
            '-source.zip', '-windows-x64.zip', '-linux-x64.tar.gz', '-linux-x64.run', '-linux-x64.AppImage')]
        sums = ''.join('a'*64 + '  ' + name + '\n' for name in names).encode()
        release = {'tag_name': tag, 'draft': False, 'assets': [
            {'name': name, 'state': 'uploaded', 'size': 1, 'digest': 'sha256:' + 'a'*64} for name in names]}
        release['assets'].append({'name': 'SHA256SUMS', 'state': 'uploaded', 'size': len(sums),
                                  'digest': 'sha256:' + hashlib.sha256(sums).hexdigest()})
        runs = [{'head_sha': 'checked', 'head_branch': tag, 'event': 'push', 'conclusion': 'success'}]
        return tag, release, sums, 'checked', runs

    def test_complete_previously_checked_release_is_eligible(self):
        validate_candidate(*self.candidate())

    def test_incomplete_or_unchecked_release_cannot_be_promoted(self):
        for fault in ('draft', 'missing', 'digest', 'duplicate', 'wrong-commit', 'wrong-tag', 'failed', 'bad-tag'):
            tag, release, sums, commit, runs = copy.deepcopy(self.candidate())
            if fault == 'draft': release['draft'] = True
            elif fault == 'missing': release['assets'].pop()
            elif fault == 'digest': release['assets'][0]['digest'] = 'sha256:' + 'b'*64
            elif fault == 'duplicate': sums += sums.splitlines(keepends=True)[0]
            elif fault == 'wrong-commit': commit = 'other'
            elif fault == 'wrong-tag': runs[0]['head_branch'] = 'v0.1.0'
            elif fault == 'failed': runs[0]['conclusion'] = 'failure'
            elif fault == 'bad-tag': tag = 'main'
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                validate_candidate(tag, release, sums, commit, runs)
