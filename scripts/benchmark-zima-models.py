#!/usr/bin/env python3
"""Compare offline English models without changing the running speech server."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

MODELS=('vosk-model-small-en-us-0.15','vosk-model-en-us-0.22-lgraph')


def benchmark(python,worker,model,sample,runner=subprocess.run):
    result=runner([str(python),str(worker),'--model',str(model),'--benchmark',str(sample)],
                  check=True,capture_output=True,text=True,timeout=300)
    report=json.loads(result.stdout.strip().splitlines()[-1])
    if report.get('kind')!='benchmark' or not isinstance(report.get('realtimeFactor'),(int,float)):
        raise ValueError('Invalid model benchmark result.')
    return dict(report,model=model.name)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('/mnt/camera-ssd/SmartKeyboard-STT'))
    parser.add_argument('--sample',type=Path)
    args=parser.parse_args()
    root=args.root.resolve(strict=True);models=root/'models'
    sample=args.sample or models/'test.wav'
    if not sample.is_file():parser.error('A sample WAV recording is required.')
    if not (root/'venv/bin/python').is_file():parser.error('Use the existing SSD speech environment.')
    available=next(int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
    if available<1536*1024:parser.error('Need 1.5 GiB available RAM for this isolated comparison.')
    if shutil.disk_usage(root).free<1024**3:parser.error('Need 1 GiB SSD space for staging.')
    spec=importlib.util.spec_from_file_location('stt_setup',Path(__file__).with_name('install-local-stt.py'))
    setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)
    models.mkdir(exist_ok=True)
    if models.is_symlink():parser.error('Unexpected model-directory symlink.')
    candidate=models/MODELS[1]
    if candidate.is_symlink():parser.error('Unexpected candidate-model symlink.')
    if not (candidate/'am/final.mdl').is_file():
        if candidate.exists():parser.error('Incomplete candidate preserved; inspect before retrying.')
        with tempfile.TemporaryDirectory(prefix='.english-comparison-',dir=str(models)) as temporary:
            temporary=Path(temporary);archive=temporary/'candidate.zip'
            setup.MODEL=MODELS[1]
            setup.download('https://alphacephei.com/vosk/models/'+MODELS[1]+'.zip',archive,200*1024*1024)
            setup.extract_model(archive,temporary)
            if not (temporary/MODELS[1]/'am/final.mdl').is_file():raise ValueError('Incomplete candidate model.')
            os.rename(temporary/MODELS[1],candidate)
    worker=Path(__file__).resolve().parent.parent/'backend/local_dictation_worker.py'
    for name in MODELS:
        print('Benchmarking '+name+' on one low-priority core…',flush=True)
        report=benchmark(root/'venv/bin/python',worker,models/name,sample)
        print(json.dumps(report,indent=2),flush=True)
    print('Comparison only. Running server, pairing, microphone, GUI and active model were NOT changed.')
    print('Use the same headset recording to compare actual voice accuracy; this sample alone cannot prove it.')


if __name__=='__main__':
    main()
