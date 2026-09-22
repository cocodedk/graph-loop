"""A unanimous model verdict cannot cover files without cards."""

import pathlib
import sys
import tempfile
import types
import unittest
from unittest import mock

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import slicer_answer
import slicer_state
import tmp_root  # noqa: F401 — temporary files are removed at exit

EXPECTED_TESTS = 5


class NamedFileCoverageTest(unittest.TestCase):
    def setUp(self):
        self.repo = pathlib.Path(tempfile.mkdtemp())
        self.backlog = self.repo / 'backlog'
        self.backlog.mkdir()
        self.source = self.repo / 'spec.md'
        self.names = [f'ui/screen{i}/Card.kt' for i in range(8)]
        self.source.write_text('\n'.join(f'Build `{name}`.' for name in self.names))
        self.rows = [{'id': f'logic{i}', 'status': 'done', 'files': [f'logic/{i}.kt']}
                     for i in range(17)]

    def answer(self):
        judge = mock.Mock(return_value=types.SimpleNamespace(ok=True, text='ACCEPT'))
        with mock.patch.object(slicer_answer.Backlog, 'tasks', return_value=self.rows):
            result = slicer_answer.run_answer(
                'result: NO_GAP\nreason: all covered\nmolecule: null\n',
                repo=self.repo, backlog=self.backlog, sources=[self.source], reviewer=judge)
        return result

    def test_seventeen_green_cards_do_not_cover_eight_missing_files(self):
        state, reason = self.answer()
        self.assertEqual('coverage_refused', state)
        for name in self.names:
            self.assertIn(name, reason)
        self.assertFalse(slicer_state.accepted(self.backlog, self.rows))

    def test_every_named_file_needs_its_own_grant(self):
        self.rows.append({'id': 'screens', 'files': self.names[:-1]})
        self.assertEqual('coverage_refused', self.answer()[0])
        self.rows[-1]['files'] = self.names
        self.assertEqual('covered', self.answer()[0])
        self.assertTrue(slicer_state.covered(self.backlog, [self.source], self.repo, self.rows))

    def test_old_model_only_record_is_not_accepted(self):
        state = {'source_digest': slicer_state.digest([self.source], self.repo),
                 'backlog_digest': slicer_state.backlog_digest(self.rows), 'review': 'ACCEPT'}
        (self.backlog / slicer_state.STATE).write_text(yaml.safe_dump(state))
        self.assertFalse(slicer_state.accepted(self.backlog, self.rows))
        self.assertFalse(slicer_state.covered(self.backlog, [self.source], self.repo, self.rows))

    def test_paths_in_prose_links_and_fences_including_absent_files(self):
        self.source.write_text('Build ./ui/New.kt:12, [screen](ui/Other.kt#view)\n'
                               '```\nui/Third.kt\n```\nand `Root.py`.')
        self.rows = [{'id': 'misleading', 'files': ['ui'], 'goal': 'ui/New.kt',
                      'uses': ['ui/Other.kt:view']}]
        state, reason = self.answer()
        self.assertEqual('coverage_refused', state)
        for name in ('ui/New.kt', 'ui/Other.kt', 'ui/Third.kt', 'Root.py'):
            self.assertIn(name, reason)

    def test_extensionless_paths_and_external_urls(self):
        self.source.write_text('Build `Dockerfile` and config/feature. '
                               'See https://example.test/help.html')
        self.rows = [{'id': 'build', 'files': ['Dockerfile', 'config/feature']}]
        self.assertEqual('covered', self.answer()[0])
        self.rows[0]['files'].remove('config/feature')
        self.assertEqual('coverage_refused', self.answer()[0])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == '__main__':
    unittest.main()
