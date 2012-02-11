#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

kajongg is free software you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
"""

import os, sys, csv, subprocess

from optparse import OptionParser

def evaluate(csvFile):
    """evaluate csvFile"""
    # TODO: dump details for the hand with the largest difference
    # between default and tested intelligence for the human player

    # pylint: disable=R0912
    # pylint says too many branches
    if not os.path.exists(csvFile):
        return
    allRows = list(csv.reader(open(csvFile,'r'), delimiter=';'))
    if not allRows:
        return
    # we want unique tuples so we can work with sets
    allRows = set(tuple(x) for x in allRows)
    games = dict()
    # build set of rows for every ai
    for aiVariant in set(x[0] for x in allRows):
        games[aiVariant] = set(x for x in allRows if x[0] == aiVariant)

    commonSeeds = None
    for aiVariant, rows in games.items():
        seeds = set(x[1] for x in rows)
        if len(seeds) != len(rows):
            print 'AI variant "%s" has different rows for seeds' % aiVariant,
            for seed in seeds:
                if len([x for x in rows if x[1] == seed]) > 1:
                    print seed,
            print
            return
        if not commonSeeds:
            commonSeeds = seeds
        else:
            commonSeeds &= seeds

    print
    print 'the 3 robot players always use the Default AI'
    print
    print 'common games:'
    print '{:<20} {:>5}     {:>4}                      human'.format('AI variant', 'games', 'points')
    for aiVariant, rows in games.items():
        print '{:<20} {:>5}  '.format(aiVariant[:20], len(commonSeeds)),
        for playerIdx in range(4):
            print '{:>8}'.format(sum(int(x[3+playerIdx*4]) for x in rows if x[1] in commonSeeds)),
        print
    print
    print 'all games:'
    for aiVariant, rows in games.items():
        if len(rows) > len(commonSeeds):
            print '{:<20} {:>5}  '.format(aiVariant[:20], len(rows)),
            for playerIdx in range(4):
                print '{:>8}'.format(sum(int(x[3+playerIdx*4]) for x in rows)),
            print

def common_options(options):
    """common options for kajonggtest.py and kajongg.py"""
    result = []
    if options.ai:
        result.append('--ai=%s' % options.ai)
    if options.playopen:
        result.append('--playopen')
    if options.showtraffic:
        result.append('--showtraffic')
    if options.showsql:
        result.append('--showsql')
    result.append('--csv=%s' % options.csv)
    result.append('--autoplay=%s' % options.ruleset)
    return result

def split_jobs(options):
    """split the wanted game range and start separate processes for the
   splits in parallel"""
    step = options.count / options.jobs
    ranges = [[options.seed + x*step, step] for x in range(0, options.jobs)]
    ranges[-1][1] += options.count - step * options.jobs
    subprocesses = []
    srcDir = os.path.dirname(sys.argv[0])
    for idx, part in enumerate(ranges):
        socketName = 'sock{}.{}.{}'.format(options.ai, idx, part[0])
        cmd = ['{}/kajonggtest.py --noeval --game={} --count={} --socket={}'.format(
             srcDir, part[0], part[1], socketName)]
        if options.gui:
            cmd.append('--gui')
        cmd.extend(common_options(options))
        cmd = ' '.join(cmd)
        print cmd
        subprocesses.append(subprocess.Popen(cmd, shell=True))
    for idx, part in enumerate(ranges):
        _ = os.waitpid(subprocesses[idx].pid, 0)[1]

def parse_options():
    """parse options"""
    parser = OptionParser()
    parser.add_option('', '--gui', dest='gui', action='store_true',
        default=False, help='show graphical user interface')
    parser.add_option('', '--autoplay', dest='ruleset',
        default='Testset', help='play like a robot using RULESET',
        metavar='RULESET')
    parser.add_option('', '--ai', dest='ai',
        default='Default', help='use AI variant',
        metavar='AI')
    parser.add_option('', '--csv', dest='csv',
        default='kajongg.csv', help='write results to CSV',
        metavar='CSV')
    parser.add_option('', '--game', dest='seed',
        help='start first game with SEED, increment for following games',
        metavar='SEED', type=int, default=1)
    parser.add_option('', '--count', dest='count',
        help='play COUNT games',
        metavar='COUNT', type=int, default=0)
    parser.add_option('', '--showtraffic', dest='showtraffic', action='store_true',
        help='show network messages', default=False)
    parser.add_option('', '--playopen', dest='playopen', action='store_true',
        help='all robots play with visible concealed tiles' , default=False)
    parser.add_option('', '--showsql', dest='showsql', action='store_true',
        help='show database SQL commands', default=False)
    parser.add_option('', '--jobs', dest='jobs',
        help='start JOBS kajongg instances simultaneously, each with a dedicated server',
        metavar='JOBS', type=int, default=1)
    parser.add_option('', '--socket', dest='socket', help='use socket for games')
    parser.add_option('', '--noeval', dest='noeval', action='store_true',
        help='do not evaluate results', default=False)
    return parser.parse_args()

def main():
    """parse options, play, evaluate results"""
    print

    (options, args) = parse_options()

    if args and ''.join(args):
        print 'unrecognized arguments:', ' '.join(args)
        sys.exit(2)

    if not options.noeval:
        evaluate(options.csv)

    if options.jobs > 1:
        split_jobs(options)
        evaluate(options.csv)
        sys.exit(0)

    try:
        for seed in range(options.seed, options.seed + options.count):
            print 'SEED=%d' % seed
            srcDir = os.path.dirname(sys.argv[0])
            cmd = ['{}/kajongg.py --game={}'.format(srcDir, seed)]
            if not options.gui:
                cmd.append('--nogui')
            if options.socket:
                cmd.append('--socket=%s' % options.socket)
            cmd.extend(common_options(options))
            cmd = ' '.join(cmd)
            print cmd
            process = subprocess.Popen(cmd, shell=True)
            _ = os.waitpid(process.pid, 0)[1]
    except KeyboardInterrupt:
        pass
    if not options.noeval and options.count > 0:
        evaluate(options.csv)


if __name__ == '__main__':
    main()
