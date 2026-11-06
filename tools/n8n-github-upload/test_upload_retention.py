"""Exercise actual SQLite state and disposable clone cleanup boundaries."""
import json
import os
import pathlib
import subprocess
import tempfile
import uuid

HERE = pathlib.Path(__file__).parent

with tempfile.TemporaryDirectory() as directory:
    root = pathlib.Path(directory)
    clones = root / 'git'
    clones.mkdir()
    env = {**os.environ, 'UPLOAD_LEDGER_DIR': str(root / 'control'), 'UPLOAD_GIT_ROOT': str(clones)}

    def call(action, payload):
        run = subprocess.run(['node', str(HERE / 'upload-ledger.cjs'), action, json.dumps(payload)], env=env, capture_output=True, text=True, check=True)
        return json.loads(run.stdout)

    def begin(owner):
        identifier = str(uuid.uuid4())
        manifest = {'uploadId': identifier, 'files': [{'field': 'f000', 'path': 'data.bin', 'bytes': 3, 'sha256': 'a' * 64}]}
        result = call('claim', {'id': identifier, 'manifest': manifest, 'owner': owner})
        assert result['route'] == 'new'
        clone = clones / ('pilot-' + identifier)
        clone.mkdir()
        (clone / 'source.bin').write_bytes(b'abc')
        return identifier, manifest, clone

    confirmed, manifest, clone = begin('one')
    call('committed', {'id': confirmed, 'owner': 'one', 'sha': 'b' * 40})
    receipt = {'uploadId': confirmed, 'commitSha': 'b' * 40, 'success': True}
    result = call('confirmed', {'id': confirmed, 'receipt': receipt})
    assert result['cleanup']['state'] == 'removed' and not clone.exists()
    assert call('read', {'id': confirmed})['receipt'] == receipt
    assert call('claim', {'id': confirmed, 'manifest': manifest, 'owner': 'retry'})['route'] == 'verify'

    uncertain, uncertain_manifest, uncertain_clone = begin('failed-before-commit')
    assert call('claim', {'id': uncertain, 'manifest': uncertain_manifest, 'owner': 'another'})['route'] == 'uncertain'
    committed, _, committed_clone = begin('failed-before-push')
    call('committed', {'id': committed, 'owner': 'failed-before-push', 'sha': 'c' * 40})
    call('prune-confirmed', {})
    assert uncertain_clone.exists() and committed_clone.exists()
    assert call('read', {'id': uncertain})['state'] == 'claimed'
    assert call('read', {'id': committed})['state'] == 'committed'

    symlinked, _, link_clone = begin('symlink')
    (link_clone / 'source.bin').unlink()
    link_clone.rmdir()
    outside = root / 'outside'
    outside.mkdir()
    (outside / 'keep').write_text('keep')
    link_clone.symlink_to(outside, target_is_directory=True)
    call('committed', {'id': symlinked, 'owner': 'symlink', 'sha': 'd' * 40})
    result = call('confirmed', {'id': symlinked, 'receipt': {'uploadId': symlinked, 'commitSha': 'd' * 40, 'success': True}})
    assert result['state'] == 'confirmed' and result['cleanup']['state'] == 'unsafe_path'
    assert (outside / 'keep').read_text() == 'keep'

    def failed_clone(name, origin='https://github.com/markmalina/freelance.git', changed=False):
        candidate = root / name
        (candidate / '.git/logs').mkdir(parents=True)
        (candidate / '.git/config').write_text('[remote "origin"]\n\turl = ' + origin + '\n')
        history = '0 1 owner 1 +0000\tclone: from ' + origin + '\n'
        if changed:
            history += '1 2 owner 2 +0000\tcommit: preserve this local work\n'
        (candidate / '.git/logs/HEAD').write_text(history)
        (candidate / 'copy.bin').write_bytes(b'abc')
        return candidate

    removable = failed_clone('.n8n-clone-' + 'a' * 24)
    wrong_origin = failed_clone('.n8n-clone-' + 'b' * 24, origin='https://github.com/other/project.git')
    local_commit = failed_clone('.n8n-clone-' + 'c' * 24, changed=True)
    absent = '.n8n-clone-' + 'd' * 24
    result = call('prune-failed-temporary', {'names': [removable.name, wrong_origin.name, local_commit.name, absent]})
    assert [row['state'] for row in result['results']] == ['removed', 'unexpected_origin', 'local_changes_in_history', 'absent']
    assert not removable.exists() and wrong_origin.exists() and local_commit.exists()

    stdin_run = subprocess.run(['node', '-', 'prune-failed-temporary', json.dumps({'names': [absent]})], input=(HERE / 'upload-ledger.cjs').read_text(), env=env, capture_output=True, text=True, check=True)
    assert json.loads(stdin_run.stdout)['results'][0]['state'] == 'absent'

    digest = 'e' * 64
    grant = call('grant', {'id': str(uuid.uuid4()), 'digest': digest, 'fileCount': 1, 'totalBytes': 3})
    assert grant['uploadUrl'].endswith('/webhook/work-fresh-token-upload-pilot-v1')
    print(json.dumps({'confirmedCloneRemoved': True, 'durableReceiptPreserved': True, 'replayStillVerifiesSameCommit': True, 'uncertainPreserved': True, 'unconfirmedCommitPreserved': True, 'symlinkTargetPreserved': True, 'failedTempRequiresExactAllowlistAndOrigin': True, 'localCommitInTemporaryClonePreserved': True, 'stdinMaintenanceWorks': True, 'grantPointsToFreshTokenEndpoint': True}))

