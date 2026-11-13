import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock

spec=importlib.util.spec_from_file_location('compare_models',Path(__file__).with_name('benchmark-zima-models.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class ModelComparisonTests(unittest.TestCase):
    def test_benchmark_uses_separate_process_with_limits(self):
        runner=Mock(return_value=subprocess.CompletedProcess([],0,json.dumps({'kind':'benchmark','realtimeFactor':0.5})))
        report=module.benchmark(Path('/venv/python'),Path('/worker.py'),Path('/models/candidate'),Path('/sample.wav'),runner)
        self.assertEqual(report['model'],'candidate')
        args=runner.call_args.args[0]
        self.assertEqual(args[-2:],['--benchmark',str(Path('/sample.wav'))])
        self.assertEqual(runner.call_args.kwargs['timeout'],300)
        self.assertTrue(runner.call_args.kwargs['check'])

    def test_worker_error_not_reported_as_valid_benchmark(self):
        runner=Mock(return_value=subprocess.CompletedProcess([],0,'{"kind":"error"}'))
        with self.assertRaises(ValueError):
            module.benchmark(Path('/python'),Path('/worker'),Path('/model'),Path('/sample'),runner)


if __name__=='__main__':unittest.main()
