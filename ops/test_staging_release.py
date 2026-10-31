"""Adapter boundary regressions. Broken target/scope cases must fail before any effect."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('release', Path(__file__).with_name('staging-release.py'))
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class Boundaries(unittest.TestCase):
    def service(self):
        return {'id': release.SERVICE, 'type': 'static_site', 'repo': release.REPOSITORY,
                'rootDir': 'reservas', 'autoDeploy': 'no', 'serviceDetails': {'publishPath': 'build/client',
                'buildCommand': 'yarn install --frozen-lockfile && yarn build', 'url': release.URL}}

    def test_target_and_build_contract(self):
        release.check_service(self.service())
        for field, value in [('id','production'), ('type','web_service'), ('repo','other'),('rootDir','api'), ('autoDeploy','yes')]:
            broken = self.service(); broken[field] = value
            with self.assertRaises(ValueError): release.check_service(broken)
        broken = self.service();broken['serviceDetails']['publishPath'] = 'build'
        with self.assertRaises(ValueError):release.check_service(broken)

    def test_ui_scope_does_not_accept_runtime_dependencies_or_backend_changes(self):
        release.check_diff(['reservas/src/App.scss','reservas/app/root.jsx'])
        for forbidden in ['reservas/package.json','reservas/yarn.lock','render.yaml','python-services/app.py']:
            with self.assertRaises(ValueError):release.check_diff([forbidden])

    def test_native_rollback_dispatches_only_the_recorded_build(self):
        adapter = release.RenderStagingUI()
        intent = {"source_sha":"a"*40, "restore_source_sha":release.BASE,
                  "restore_artifact_id":"dep-oldbuild", "target":release.SERVICE}
        observed = {"deploy_id":"dep-restored", "probes_verified":True, "probe_results":[]}
        with patch.object(release, "api", return_value={"id":"dep-restored"}) as remote, \
             patch.object(adapter, "wait", return_value=observed):
            result = adapter.rollback(root=None, job_id="j", job={}, manifest={}, assessment={"effect_intent":intent})
        remote.assert_called_once_with(f"/services/{release.SERVICE}/rollback", "POST", {"deployId":"dep-oldbuild"})
        self.assertEqual(result["restored_artifact_id"], "dep-oldbuild")
        self.assertEqual(result["source_sha"], "a"*40)
        self.assertEqual(result["restored_source_sha"], release.BASE)

    def test_reconcile_does_not_replay_or_match_a_deploy_before_dispatch(self):
        adapter = release.RenderStagingUI()
        previous = {"id":"dep-old", "commit":{"id":"a"*40}, "createdAt":"2020-01-01T00:00:00Z", "status":"live"}
        effect = {"kind":"updates.deploy", "created_at":1700000000, "intent":{"source_sha":"a"*40}}
        with patch.object(release, "deploys", return_value=[previous]), patch.object(release, "api") as remote:
            result = adapter.reconcile_recorded(root=None, job_id="j", job={}, effect=effect)
        self.assertFalse(result["reconciled"])
        remote.assert_not_called()


if __name__ == '__main__':unittest.main()
