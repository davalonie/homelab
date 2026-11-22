"""Fault injection into a disposable project; Docker is simulated, never called."""
import base64
import errno
import json
import multiprocessing
import os
import runpy
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from test_backups import restore

SOURCE = Path(__file__).resolve().parents[1] / 'scripts/backup.py'

@pytest.fixture
def project(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    (root / 'scripts').mkdir(parents=True)
    script = root / 'scripts/backup.py'
    shutil.copyfile(SOURCE, script)
    (root / 'runtime/music').mkdir(parents=True)
    (root / 'runtime/music/tone').write_bytes(b'original fixture')
    (root / 'secrets').mkdir()
    key = root / 'secrets/backup.key'
    key.write_bytes(base64.urlsafe_b64encode(os.urandom(32)))
    commands = []
    def docker(args, **kw):
        assert args[0] == 'docker'
        commands.append(args[1])
        if args[1] == 'ps': return 'fictional-id\n'
        if args[1] == 'inspect':
            return json.dumps([{'Image':'sha256:fixture','Config':{'Labels':{
                'com.docker.compose.project.working_dir':str(root),
                'com.docker.compose.service':'music'}}}])
        assert args[1] in ('start','stop')
        return ''
    monkeypatch.setattr(subprocess, 'check_output', docker)
    def create(path=None):
        path = path or root / 'backups/fixture.mhb'
        monkeypatch.setattr(sys,'argv',[str(script),'create',str(path)])
        runpy.run_path(str(script),run_name='__main__')
        return path
    return root, key, commands, create


def test_hardlinked_music_creates_a_restorable_archive(project, tmp_path):
    root,key,commands,create=project
    os.link(root/'runtime/music/tone',root/'runtime/music/second')
    path=create()
    target=tmp_path/'restored'
    assert restore(path,key,target).returncode==0
    assert (target/'runtime/music/second').read_bytes()==b'original fixture'
    assert not (target/'secrets/backup.key').exists()
    assert not (target/'.backup.lock').exists()
    assert commands[-2:]==['stop','start']

@pytest.mark.parametrize('failure',[OSError(errno.ENOSPC,'synthetic full disk'),KeyboardInterrupt()])
def test_failed_creation_never_publishes_final_name_and_restarts_writers(project,monkeypatch,failure):
    root,key,commands,create=project
    def fail(*a,**kw):raise failure
    monkeypatch.setattr(tarfile.TarFile,'add',fail)
    with pytest.raises(type(failure)):create()
    assert not (root/'backups/fixture.mhb').exists()
    assert not list((root/'backups').iterdir())
    assert commands[-2:]==['stop','start']
    assert (root/'runtime/music/tone').read_bytes()==b'original fixture'


def test_backup_destination_inside_sources_is_rejected_before_stopping(project):
    root,key,commands,create=project
    with pytest.raises((ValueError,SystemExit)):create(root/'runtime/self.mhb')
    assert 'stop' not in commands
    assert not (root/'runtime/self.mhb').exists()


def test_special_file_rejected_before_archive_is_published(project):
    root,key,commands,create=project
    os.mkfifo(root/'runtime/music/pipe')
    with pytest.raises((RuntimeError,ValueError)):create()
    assert not (root/'backups/fixture.mhb').exists()
    assert commands[-1]=='start'


def test_failed_extraction_does_not_leave_an_apparently_restored_project(tmp_path,monkeypatch):
    from test_backups import archive
    file,key=archive(tmp_path)
    dest=tmp_path/'restore'
    def fail(self,target,**kw):
        (Path(target)/'partial').write_bytes(b'partial')
        raise OSError(errno.ENOSPC,'synthetic full disk')
    monkeypatch.setattr(tarfile.TarFile,'extractall',fail)
    monkeypatch.setattr(sys,'argv',[str(SOURCE),'restore',str(file),'--key',str(key),'--target',str(dest)])
    with pytest.raises(OSError):runpy.run_path(str(SOURCE),run_name='__main__')
    assert not dest.exists() and not list(tmp_path.glob('.music-restore-*'))
    assert file.exists()


def test_overlapping_captures_reject_second_before_docker_and_release_after_publication(project):
    root,key,commands,create=project
    ctx=multiprocessing.get_context('fork')
    capturing=ctx.Event()
    release=ctx.Event()
    results=ctx.Queue()
    original_add=tarfile.TarFile.add
    def capture(name,pause):
        commands.clear()
        def add(self,*args,**kwargs):
            if pause and not capturing.is_set():
                capturing.set()
                assert release.wait(10), 'test capture was never released'
            return original_add(self,*args,**kwargs)
        tarfile.TarFile.add=add
        try:
            create(root/'backups'/name)
        except BaseException as error:
            results.put((name,type(error).__name__,str(error),list(commands)))
        else:
            results.put((name,'success','',list(commands)))
    first=ctx.Process(target=capture,args=('first.mhb',True))
    second=ctx.Process(target=capture,args=('second.mhb',False))
    first.start()
    try:
        assert capturing.wait(10), 'first capture never reached archive read'
        second.start()
        second.join(5)
        assert not second.is_alive(), 'overlap must reject immediately instead of waiting'
        second_result=results.get(timeout=2)
    finally:
        release.set()
        for process in (first,second):
            if process.pid is not None:
                process.join(10)
                if process.is_alive():
                    process.kill();process.join(2)
    first_result=results.get(timeout=2)
    print('Interleaved captures:',second_result,first_result)
    assert second_result[0]=='second.mhb'
    assert second_result[1]=='RuntimeError' and 'already running' in second_result[2]
    assert second_result[3]==[], 'second capture must not invoke Docker'
    assert first_result[0:2]==('first.mhb','success')
    assert first_result[3]==['ps','inspect','stop','start']
    assert (root/'backups/first.mhb').is_file() and not (root/'backups/second.mhb').exists()
    create(root/'backups/after.mhb')
    assert (root/'backups/after.mhb').is_file(), 'the completed capture must release its lock'


@pytest.mark.parametrize('kind',['symlink','fifo'])
def test_unsafe_lock_file_is_rejected_before_docker(project,tmp_path,kind):
    root,key,commands,create=project
    lock=root/'.backup.lock'
    outside=tmp_path/'unrelated'
    outside.write_bytes(b'untouched')
    if kind=='symlink':lock.symlink_to(outside)
    else:os.mkfifo(lock)
    with pytest.raises((OSError,RuntimeError)):create()
    assert commands==[]
    assert outside.read_bytes()==b'untouched'
    assert not (root/'backups/fixture.mhb').exists()
