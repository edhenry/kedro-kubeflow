import unittest

import yaml
from pydantic import ValidationError

from kedro_kubeflow.config import PluginConfig
from tests.common import MinimalConfigMixin

CONFIG_YAML = """
host: https://example.com
run_config:
  image: "gcr.io/project-image/test"
  image_pull_policy: "Always"
  experiment_name: "Test Experiment"
  run_name: "test run"
  scheduled_run_name: "scheduled run"
  description: "My awesome pipeline"
  wait_for_completion: True
  ttl: 300
  volume:
    storageclass: default
    size: 3Gi
    access_modes: [ReadWriteOnce]
    keep: True
"""


class TestPluginConfig(unittest.TestCase, MinimalConfigMixin):
    def test_plugin_config(self):
        cfg = PluginConfig(**yaml.safe_load(CONFIG_YAML))
        self.assertEqual(cfg.host, "https://example.com")
        self.assertEqual(cfg.run_config.image, "gcr.io/project-image/test")
        self.assertEqual(cfg.run_config.image_pull_policy, "Always")
        self.assertEqual(cfg.run_config.experiment_name, "Test Experiment")
        self.assertEqual(cfg.run_config.run_name, "test run")
        self.assertEqual(cfg.run_config.scheduled_run_name, "scheduled run")
        self.assertTrue(cfg.run_config.wait_for_completion)
        self.assertEqual(cfg.run_config.volume.storageclass, "default")
        self.assertEqual(cfg.run_config.volume.size, "3Gi")
        self.assertTrue(cfg.run_config.volume.keep)
        self.assertEqual(cfg.run_config.volume.access_modes, ["ReadWriteOnce"])
        self.assertIsNotNone(cfg.run_config.resources["node1"])
        self.assertIsNotNone(cfg.run_config.resources["__default__"])
        self.assertEqual(cfg.run_config.description, "My awesome pipeline")
        self.assertEqual(cfg.run_config.ttl, 300)

    def test_defaults(self):
        cfg = PluginConfig(**self.minimal_config())
        self.assertEqual(cfg.run_config.image_pull_policy, "IfNotPresent")
        assert cfg.run_config.description is None
        SECONDS_IN_ONE_WEEK = 3600 * 24 * 7
        self.assertEqual(cfg.run_config.ttl, SECONDS_IN_ONE_WEEK)
        assert cfg.run_config.volume is None

    def test_missing_required_config(self):
        with self.assertRaises(ValidationError):
            PluginConfig(**{})

    def test_resources_default_only(self):
        cfg = PluginConfig(
            **self.minimal_config(
                {"run_config": {"resources": {"__default__": {"cpu": "100m"}}}}
            )
        )
        self.assertEqual(cfg.run_config.resources["node2"]["cpu"], "100m")
        self.assertEqual(cfg.run_config.resources["node3"]["cpu"], "100m")

    def test_resources_gpu_label(self):
        cfg = PluginConfig(
            **self.minimal_config(
                {
                    "run_config": {
                        "resources": {
                            "__default__": {
                                "cpu": "100m",
                                "nvidia.com/gpu": "1",
                                "nvidia.com/tpu": "1",
                            }
                        }
                    }
                }
            )
        )
        self.assertEqual(
            cfg.run_config.resources["__default__"]["nvidia.com/gpu"], "1"
        )
        self.assertEqual(
            cfg.run_config.resources["node3"]["nvidia.com/tpu"], "1"
        )

    def test_resources_no_default(self):
        cfg = PluginConfig(
            **self.minimal_config(
                {"run_config": {"resources": {"node2": {"cpu": "100m"}}}}
            )
        )
        self.assertEqual(cfg.run_config.resources["node2"]["cpu"], "100m")
        self.assertDictEqual(
            cfg.run_config.resources["node3"],
            cfg.run_config.resources["__default__"],
        )

    def test_resources_default_and_node_specific(self):
        cfg = PluginConfig(
            **self.minimal_config(
                {
                    "run_config": {
                        "resources": {
                            "__default__": {"cpu": "200m", "memory": "64Mi"},
                            "node2": {"cpu": "100m"},
                        }
                    }
                }
            )
        )
        self.assertDictEqual(
            cfg.run_config.resources["node2"],
            {
                "cpu": "100m",
                "memory": "64Mi",
            },
        )
        self.assertDictEqual(
            cfg.run_config.resources["node3"],
            {
                "cpu": "200m",
                "memory": "64Mi",
            },
        )

    def test_tolerations_default_only(self):
        toleration_config = [
            {
                "key": "thekey",
                "operator": "equal",
                "value": "thevalue",
                "effect": "NoSchedule",
            }
        ]
        cfg = PluginConfig(
            **self.minimal_config(
                {
                    "run_config": {
                        "tolerations": {"__default__": toleration_config}
                    }
                }
            )
        )

        self.assertDictEqual(
            cfg.run_config.tolerations["node2"][0].dict(), toleration_config[0]
        )
        self.assertDictEqual(
            cfg.run_config.tolerations["node3"][0].dict(), toleration_config[0]
        )

    def test_tolerations_no_default(self):
        toleration_config = [
            {
                "key": "thekey",
                "operator": "equal",
                "value": "thevalue",
                "effect": "NoSchedule",
            }
        ]
        cfg = PluginConfig(
            **self.minimal_config(
                {"run_config": {"tolerations": {"node2": toleration_config}}}
            )
        )

        self.assertDictEqual(
            cfg.run_config.tolerations["node2"][0].dict(), toleration_config[0]
        )

        self.assertEqual(
            isinstance(cfg.run_config.tolerations["node2"], list)
            and len(cfg.run_config.tolerations["node2"]),
            1,
        )
        self.assertEqual(
            isinstance(cfg.run_config.tolerations["node3"], list)
            and len(cfg.run_config.tolerations["node3"]),
            0,
        )

    def test_tolerations_default_and_node_specific(self):
        toleration_config = [
            {
                "key": "thekey",
                "operator": "equal",
                "value": "thevalue",
                "effect": "NoSchedule",
            }
        ]
        default_toleration_config = [
            {
                "key": "thekeyfordefault",
                "operator": "equal",
                "value": "thevaluefordefault",
                "effect": "NoSchedule",
            }
        ]
        cfg = PluginConfig(
            **self.minimal_config(
                {
                    "run_config": {
                        "tolerations": {
                            "__default__": default_toleration_config,
                            "node2": toleration_config,
                        }
                    }
                }
            )
        )

        self.assertDictEqual(
            cfg.run_config.tolerations["node2"][0].dict(), toleration_config[0]
        )
        self.assertDictEqual(
            cfg.run_config.tolerations["node3"][0].dict(),
            default_toleration_config[0],
        )

    def test_do_not_keep_volume_by_default(self):
        cfg = PluginConfig(
            **self.minimal_config(override={"run_config": {"volume": {}}})
        )
        assert cfg.run_config.volume.keep is False

    def test_reuse_run_name_for_scheduled_run_name(self):
        cfg = PluginConfig(
            **self.minimal_config({"run_config": {"run_name": "some run"}})
        )
        self.assertEqual(cfg.run_config.run_name, "some run")
        self.assertEqual(cfg.run_config.scheduled_run_name, "some run")

    def test_retry_policy_default_and_node_specific(self):
        cfg = PluginConfig(
            **self.minimal_config(
                {
                    "run_config": {
                        "retry_policy": {
                            "__default__": {
                                "num_retries": 4,
                                "backoff_duration": "60s",
                                "backoff_factor": 2,
                            },
                            "node3": {
                                "num_retries": "100",
                                "backoff_duration": "5m",
                                "backoff_factor": 1,
                            },
                        }
                    }
                }
            )
        )

        self.assertDictEqual(
            cfg.run_config.retry_policy["node2"].dict(),
            {
                "backoff_duration": "60s",
                "backoff_factor": 2,
                "num_retries": 4,
            },
        )

        self.assertDictEqual(
            cfg.run_config.retry_policy["node3"].dict(),
            {
                "backoff_duration": "5m",
                "backoff_factor": 1,
                "num_retries": 100,
            },
        )

    def test_retry_policy_no_default(self):
        cfg = PluginConfig(
            **self.minimal_config(
                {
                    "run_config": {
                        "retry_policy": {
                            "node3": {
                                "num_retries": "100",
                                "backoff_duration": "5m",
                                "backoff_factor": 1,
                            },
                        }
                    }
                }
            )
        )

        self.assertDictEqual(
            cfg.run_config.retry_policy["node3"].dict(),
            {
                "num_retries": 100,
                "backoff_duration": "5m",
                "backoff_factor": 1.0,
            },
        )

        self.assertIsNone(cfg.run_config.retry_policy["node2"])
