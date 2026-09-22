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

EXPECTED_TESTS = 7


class NamedFileCoverageTest(unittest.TestCase):
    def setUp(self):
        self.repo = pathlib.Path(tempfile.mkdtemp())
        self.backlog = self.repo / 'backlog'
        self.backlog.mkdir()
        self.source = self.repo / 'spec.md'
        self.names = [f'ui/screen{i}/Card.kt' for i in range(8)]
        self.source.write_text('\n'.join(
            f'## Node {i}\nFiles: `{name}`' for i, name in enumerate(self.names)))
        self.rows = [{'id': f'logic{i}', 'status': 'done', 'files': [f'logic/{i}.kt']}
                     for i in range(17)]

    def create_files(self, names):
        for name in names:
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()

    def answer(self):
        judge = mock.Mock(return_value=types.SimpleNamespace(ok=True, text='ACCEPT'))
        with mock.patch.object(slicer_answer.Backlog, 'tasks', return_value=self.rows):
            result = slicer_answer.run_answer(
                'result: NO_GAP\nreason: all covered\nmolecule: null\n',
                repo=self.repo, backlog=self.backlog, sources=[self.source], reviewer=judge)
        return result

    def test_seventeen_green_cards_do_not_cover_eight_ungranted_files(self):
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

    def test_mentions_and_fenced_fields_contribute_no_names(self):
        self.source.write_text('Build `ui/New.kt`. [screen](ui/Other.kt)\n'
                               '```markdown\nFiles: ui/Third.kt\n```\n'
                               '~~~~\nCreates: ui/Fourth.kt\n~~~~\n'
                               '<!-- Files: ui/Hidden.kt -->\n'
                               'The Files: ui/Prose.kt are examples.\n')
        self.create_files(['ui/New.kt', 'ui/Other.kt', 'ui/Third.kt'])
        self.rows = []
        self.assertEqual('covered', self.answer()[0])

    def test_structured_fields_include_absent_and_extensionless_files(self):
        self.source.write_text('- **Files:** `Dockerfile`, ./config/feature\n'
                               '**Creates**: [[ui/New.kt:Screen]]\n'
                               'Files:\n  - Root.py\n  - ui/Other.kt\n')
        names = ['Dockerfile', 'config/feature', 'ui/New.kt', 'Root.py', 'ui/Other.kt']
        self.rows = []
        state, reason = self.answer()
        self.assertEqual('coverage_refused', state)
        for name in names:
            self.assertIn(name, reason)
        self.rows = [{'id': 'build', 'files': names}]
        self.assertEqual('covered', self.answer()[0])

    def test_links_and_sentences_are_not_work_lists(self):
        self.source.write_text('Files: [reference](docs/DESIGN.md)\n'
                               'Creates: see ui/Example.kt for details.\n'
                               'Files: https://example.test/help.html\n')
        self.rows = []
        self.assertEqual('covered', self.answer()[0])

    def test_previous_existence_filtered_record_cannot_prove_coverage(self):
        state = {'source_digest': slicer_state.digest([self.source], self.repo),
                 'backlog_digest': slicer_state.backlog_digest(self.rows),
                 'named_files': [], 'review': 'ACCEPT'}
        (self.backlog / slicer_state.STATE).write_text(yaml.safe_dump(state))
        self.assertFalse(slicer_state.accepted(self.backlog, self.rows))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == '__main__':
    unittest.main()
