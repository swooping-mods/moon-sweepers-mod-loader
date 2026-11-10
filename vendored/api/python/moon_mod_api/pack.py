"""Create a local .msmod from a manifest and complete original payload directory."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import zipfile
from .packages import examine,validate
from .storage import load,is_alias


def pack(manifest_path,payload,output):
    payload=Path(payload).resolve();output=Path(output).absolute()
    if not payload.is_dir() or output.resolve().is_relative_to(payload): raise ValueError('Keep the output package outside its payload folder')
    manifest=load(manifest_path);files={}
    for directory,dirs,names in os.walk(payload,followlinks=False):
        for name in dirs+names:
            if is_alias(Path(directory)/name):raise ValueError('Payload symlinks/reparse points are not accepted')
        for name in names:
            path=Path(directory)/name;files[path.relative_to(payload).as_posix()]=path.read_bytes()
    if 'manifest.json' in files:raise ValueError('Pass the manifest separately from the payload')
    manifest['files']={name:hashlib.sha256(data).hexdigest() for name,data in files.items()}
    validate(manifest)
    files['manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent,delete=False) as temporary:stage=Path(temporary.name)
    try:
        with zipfile.ZipFile(stage,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
            for name,data in sorted(files.items()):
                info=zipfile.ZipInfo(name,(2026,11,9,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;archive.writestr(info,data)
        examine(stage)
        # Packages are immutable author outputs; use another filename for an upgrade.
        if output.exists():
            if output.read_bytes()!=stage.read_bytes():raise ValueError('Output already contains a different package')
        else:stage.rename(output)
    finally:stage.unlink(missing_ok=True)
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('manifest',type=Path);parser.add_argument('payload',type=Path);parser.add_argument('output',type=Path);args=parser.parse_args()
    print(pack(args.manifest,args.payload,args.output));return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError) as error:print(str(error),file=sys.stderr);raise SystemExit(1)
