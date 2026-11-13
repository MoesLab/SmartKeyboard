#!/usr/bin/env python3
"""Install isolated English Vosk and benchmark one CPU core before enabling it."""
import argparse
import json
import os
from pathlib import Path,PurePosixPath
import shutil
import stat
import subprocess
import sys
import tempfile
from urllib.request import urlopen
import venv
import zipfile

MODEL='vosk-model-small-en-us-0.15'


def download(url,target,limit):
    print('Downloading',target.name,flush=True);size=0
    partial=target.with_name(target.name+'.part')
    with urlopen(url,timeout=40) as response, partial.open('wb') as output:
        if not response.geturl().startswith('https://'):raise ValueError('HTTPS download required.')
        while True:
            chunk=response.read(1024*1024)
            if not chunk:break
            size+=len(chunk)
            if size>limit:raise ValueError('Unexpectedly large download.')
            output.write(chunk)
    os.replace(partial,target)


def extract_model(archive,directory):
    with zipfile.ZipFile(archive) as zipped:
        entries=zipped.infolist()
        if len(entries)>2000 or sum(entry.file_size for entry in entries)>500*1024*1024:raise ValueError('Unexpected model archive size.')
        for entry in entries:
            path=PurePosixPath(entry.filename)
            if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0]!=MODEL or '\\' in entry.filename or stat.S_ISLNK(entry.external_attr>>16):raise ValueError('Unsafe model archive entry.')
        zipped.extractall(directory)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--allow-slow',action='store_true')
    args=parser.parse_args()
    if sys.platform!='linux' or os.geteuid()==0:parser.error('Run on Radxa as radxa, without sudo.')
    app=Path.home()/'SmartKeyboard';environment=app/'.venv-stt';models=app/'models';configuration=app/'config/local-stt.json'
    try:
        available=next(int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
        print('Available RAM:',available//1024,'MiB',flush=True)
        if available<512*1024:raise ValueError('Less than 512 MiB available. Leave local recognition disabled until memory headroom is checked.')
        if any(path.is_symlink() for path in (app,environment,models,configuration,configuration.parent)):raise ValueError('Unexpected project symlink.')
        if shutil.disk_usage(app).free<1024**3:raise ValueError('At least 1 GiB free space is required for isolated setup and download staging.')
        if environment.exists() and not (environment/'pyvenv.cfg').is_file():raise ValueError('Unrecognized existing .venv-stt directory.')
        if not (environment/'bin/python').is_file() or subprocess.run([str(environment/'bin/python'),'-m','pip','--version'],capture_output=True).returncode!=0:
            print('Creating isolated speech environment…',flush=True)
            try:venv.EnvBuilder(with_pip=True).create(environment)
            except Exception:raise ValueError('Python venv support is missing. Run sudo apt-get install python3-venv, then retry. No system Python package is replaced.')
        python=environment/'bin/python'
        subprocess.run([str(python),'-m','pip','install','vosk==0.3.45'],check=True)
        models.mkdir(exist_ok=True)
        if not (models/MODEL/'am/final.mdl').is_file():
            if (models/MODEL).exists():raise ValueError('Incomplete existing model directory; preserve and inspect it before retrying.')
            with tempfile.TemporaryDirectory(prefix='.stt-download-',dir=str(models)) as temporary:
                temporary=Path(temporary);archive=temporary/'model.zip'
                download('https://alphacephei.com/vosk/models/'+MODEL+'.zip',archive,100*1024*1024)
                extract_model(archive,temporary)
                if not (temporary/MODEL/'am/final.mdl').is_file():raise ValueError('Downloaded model is incomplete.')
                os.rename(temporary/MODEL,models/MODEL)
        sample=models/'stt-benchmark.wav'
        if not sample.is_file():download('https://raw.githubusercontent.com/alphacep/vosk-api/master/python/example/test.wav',sample,10*1024*1024)
        worker=Path(__file__).resolve().parent.parent/'backend/local_dictation_worker.py'
        print('Benchmarking offline English recognition on one lower-priority CPU core…',flush=True)
        result=subprocess.run([str(python),str(worker),'--model',str(models/MODEL),'--benchmark',str(sample)],text=True,capture_output=True,check=True,timeout=180)
        report=json.loads(result.stdout.strip().splitlines()[-1]);enabled=report['realtimeFactor']<=1 or args.allow_slow
        configuration.parent.mkdir(exist_ok=True)
        configuration.write_text(json.dumps({'version':1,'language':'en-US','enabled':enabled,'benchmark':report},indent=2));configuration.chmod(0o600)
        print(json.dumps(report,indent=2))
        print('Local dictation enabled.' if enabled else 'Local installed but DISABLED: slower than real time. Keep the working keyboard, review this report, or explicitly opt in with --allow-slow.')
        print('No microphone was opened for this benchmark. Runtime dictation is offline; cloud is not configured.')
        return 0
    except (OSError,ValueError,StopIteration,subprocess.SubprocessError) as error:
        print('Local STT setup stopped:',error,file=sys.stderr)
        if isinstance(error,subprocess.CalledProcessError) and error.stdout:print(str(error.stdout)[-800:],file=sys.stderr)
        return 1


if __name__=='__main__':raise SystemExit(main())
