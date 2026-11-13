import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile


def load(name,file):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(file))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


setup=load('local_stt_setup','install-local-stt.py')
checkpoint=load('stt_checkpoint','stt-checkpoint.py')


class SetupTests(unittest.TestCase):
    def test_model_archive_rejects_traversal_before_extracting(self):
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory);archive=directory/'model.zip'
            with zipfile.ZipFile(archive,'w') as zipped:zipped.writestr('../outside','bad')
            with self.assertRaises(ValueError):setup.extract_model(archive,directory)
            self.assertFalse((directory.parent/'outside').exists())

    def test_valid_model_archive_extracts_only_under_model_root(self):
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory);archive=directory/'model.zip'
            with zipfile.ZipFile(archive,'w') as zipped:zipped.writestr(setup.MODEL+'/am/final.mdl','model fixture')
            setup.extract_model(archive,directory)
            self.assertEqual((directory/setup.MODEL/'am/final.mdl').read_text(),'model fixture')

    def test_checkpoint_restores_code_not_profiles_models_or_drafts(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);app=base/'SmartKeyboard'
            for name in ('src','backend','scripts'):
                (app/name).mkdir(parents=True);(app/name/'example').write_text('before')
            (app/'kiosk-profile').mkdir();(app/'kiosk-profile/data').write_text('saved buttons and draft')
            (app/'models').mkdir();(app/'models/example').write_text('model')
            with patch.object(checkpoint.Path,'home',return_value=base),patch.object(checkpoint.os,'geteuid',return_value=1000,create=True),patch.object(sys,'argv',['checkpoint']),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(checkpoint.main(),0)
            backup=next((app/'backups').glob('pre-stt-*'))
            (app/'src/example').write_text('after')
            with patch.object(checkpoint.Path,'home',return_value=base),patch.object(checkpoint.os,'geteuid',return_value=1000,create=True),patch.object(sys,'argv',['checkpoint','--restore',str(backup)]),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(checkpoint.main(),0)
            self.assertEqual((app/'src/example').read_text(),'before')
            self.assertEqual((app/'kiosk-profile/data').read_text(),'saved buttons and draft')
            self.assertEqual((app/'models/example').read_text(),'model')


if __name__=='__main__':unittest.main()
