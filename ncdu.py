#!/usr/bin/env python2
'''

ncdu.py scans a given directory and exports json that can be fed to ncdu
(https://dev.yorhel.nl/ncdu)

It also allows to use time and name-based filters:
  --newer-than D    = only include files modified less than D days ago
  --older-than D    = only include files modified at least D days ago
  --exclude PATTERN = works the same way as in ncdu, may be specified
                      multiple times

Scanning is significantly slower than with ncdu but you may still find
this useful on machines/platform when compilation may be difficult/impossible
while python is available.

Example usage:

# browse files modified in the last 5 days
./ncdu.py --newer-than 5 /home | ncdu -f -
'''

from logging import debug
from os import walk, stat, chdir, getcwd
from os.path import basename as bn
from pprint import pprint
from time import time
import argparse
import fnmatch
import json
import logging
import os.path
import stat as _stat
import sys


def check_if_excluded(e):
    ''' returns True if file/dir is excluded, otherwise Flase '''
    if args.exclude:
        for pattern in args.exclude:
            if fnmatch.filter([e], pattern): return True
    return False


def check_dir(entry):
    path = entry.get('path')
    notreg = entry.get('notreg')
    debug('path: {path}, notreg: {notreg}'.format(**locals()))
    # is this directory a symbolic link?
    if notreg:
        entry['asize'] = 0
        entry['dsize'] = 0
        return entry
    ret = []

    for rootname, dirnames, filenames in walk(path):
        dirnames = list(dirnames)
        debug('dirnames in {path}: {dirnames}'.format(**locals()))
        ret = [entry]
        fentries = []

        for dirname in dirnames:
            debug('processing dir {dirname}..'.format(**locals()))
            metadata = stat(os.path.join(path, dirname))

            if check_if_excluded(dirname):
                debug("Not descending to this directory since it's excluded".format(**locals()))
                continue

            asize = metadata.st_size
            dsize = metadata.st_blocks * 512
            dev = metadata.st_dev
            inode = metadata.st_ino
            notreg = _stat.S_ISLNK(stat(os.path.join(path, dirname)).st_mode)
            dentry = {"path": os.path.join(path, dirname),
                      "name": bn(dirname),
                      "asize": asize,
                      "dsize": dsize,
                      "dev": dev,
                      "notreg": notreg,
                      "ino": inode}
            ret.extend([check_dir(dentry)])

        for filename in filenames:
            try:
                metadata = stat(os.path.join(path, filename))
            except:
                # skip files that cannot be read
                continue

            excluded = False
            asize = metadata.st_size
            dsize = metadata.st_blocks * 512
            dev = metadata.st_dev
            mode = metadata.st_mode
            inode = metadata.st_ino
            mtime = int(metadata.st_mtime)
            notreg = not _stat.S_ISREG(mode)

            if check_if_excluded(filename):
                debug("Resetting {filename}'s size to 0 because of exclude pattern match".format(**locals()))
                asize = 0
                dsize = 0
                excluded = True

            if args.older_than and (now - mtime) <= int(args.older_than) * 3600 * 24:
                debug('Skipping {filename} due to older_than condition'.format(**locals()))
                continue

            if args.newer_than and (now - mtime) >= int(args.newer_than) * 3600 * 24:
                debug('Skipping {filename} due to newer_than condition'.format(**locals()))
                continue

            fentry = {"path": os.path.join(path, filename),
                      "name": filename,
                      "asize": asize,
                      "dsize": dsize,
                      "notreg": notreg,
                      "mode": mode,
                      "dev": dev,
                      "mtime": mtime,
                      "ino": inode}
            if metadata.st_nlink > 1:
                fentry['hlnkc'] = True
            if excluded:
                fentry['excluded'] = 'pattern'
            debug('filename: {filename}'.format(**locals()))
            fentries.append(fentry)

        debug('fentries: {fentries}'.format(**locals()))
        if fentries: ret.extend(fentries)

        debug('returning: {ret}'.format(**locals()))
        return ret

    # looks like the path is unreadable (permission issue?)
    entry['read_error'] = True
    return entry

parser = argparse.ArgumentParser()
parser.add_argument('path', nargs=1, help='Path to search in')
parser.add_argument('-d', dest='debug', action='store_true', help='Debug mode')
parser.add_argument('-o', dest='outfile',  help='write output to file (default: STDOUT)')
parser.add_argument('--older-than', dest='older_than',  metavar='D', help='only include files older than D days', default=0)
parser.add_argument('--newer-than', dest='newer_than',  metavar='D', help='only include files newer than D days', default=99999999)
parser.add_argument('--exclude', dest='exclude',  metavar='PATTERN', action='append', help='exclude files that match PATTERN (may be specified multiple times)')

args = parser.parse_args()
path = args.path[0]

if args.debug:
    logging.basicConfig(level=logging.DEBUG)

root = {'name': path, 'path': path,
        'asize': 4096,
        'dsize': 4096,
        'dev': 1,
        'ino': 1}

now = int(time())
data = check_dir(root)
output = [1, 1, {"progname": "ncdu",
                 "progver": "1.15.1",
                 "timestamp": now}, data]

if args.outfile:
    outfile = args.outfile
    if outfile == '-': 
        print(json.dumps(output))
    else:
        with open(outfile, 'w') as f:
            f.write(json.dumps(output))
else:
    print(json.dumps(output))
