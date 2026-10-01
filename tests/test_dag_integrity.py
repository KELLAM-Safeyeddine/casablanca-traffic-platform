"""Contrats Airflow exécutés dans Docker avec unittest, sans pytest dans l'image."""

import importlib.util
import os
import unittest
from pathlib import Path


class DagIntegrityTests(unittest.TestCase):
    """Vérifier import, cycles, mapping, callbacks et chaîne de Datasets."""

    @classmethod
    def setUpClass(cls) -> None:
        if importlib.util.find_spec("airflow") is None:
            raise unittest.SkipTest("Airflow est testé dans Docker uniquement")
        from airflow.models import DagBag

        root = Path(os.environ.get("AIRFLOW_DAGS_TEST_ROOT", "/opt/airflow/dags"))
        cls.bag = DagBag(str(root), include_examples=False)

    def test_imports_and_cycles(self) -> None:
        from airflow.utils.dag_cycle_tester import check_cycle

        self.assertEqual(self.bag.import_errors, {})
        self.assertEqual(set(self.bag.dags), {
            "bootstrap_dimensions", "ingest_traffic", "data_quality", "build_marts",
        })
        for dag in self.bag.dags.values():
            check_cycle(dag)

    def test_mapping_and_failure_policy(self) -> None:
        from airflow.models.mappedoperator import MappedOperator

        ingest = self.bag.dags["ingest_traffic"]
        for task_id in ("extract_partition", "validate_traffic", "load_traffic"):
            self.assertIsInstance(ingest.get_task(task_id), MappedOperator)
        for dag in self.bag.dags.values():
            self.assertEqual(dag.max_active_runs, 1)
            self.assertFalse(dag.catchup)
            for task in dag.tasks:
                self.assertEqual(task.retries, 2)
                self.assertTrue(task.retry_exponential_backoff)
                self.assertTrue(callable(task.on_failure_callback))
        self.assertIsNone(self.bag.dags["bootstrap_dimensions"].schedule_interval)

    def test_dataset_dependencies(self) -> None:
        from airflow.timetables.simple import DatasetTriggeredTimetable

        ingest = self.bag.dags["ingest_traffic"]
        quality = self.bag.dags["data_quality"]
        marts = self.bag.dags["build_marts"]
        self.assertEqual([d.uri for d in ingest.get_task("reconcile_raw").outlets],
                         ["casatraffic://warehouse/core"])
        self.assertIsInstance(quality.timetable, DatasetTriggeredTimetable)
        self.assertEqual([d.uri for d in quality.timetable.dataset_condition.objects],
                         ["casatraffic://warehouse/core"])
        self.assertEqual([d.uri for d in quality.get_task("audit").outlets],
                         ["casatraffic://warehouse/quality_passed"])
        self.assertIsInstance(marts.timetable, DatasetTriggeredTimetable)
        self.assertEqual([d.uri for d in marts.timetable.dataset_condition.objects],
                         ["casatraffic://warehouse/quality_passed"])
        upstream = ingest.get_task("reconcile_raw").upstream_task_ids
        self.assertIn("load_traffic", upstream)


if __name__ == "__main__":
    unittest.main(verbosity=2)
