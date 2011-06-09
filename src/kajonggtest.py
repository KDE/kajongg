#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2011 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

def evaluate():
    """evaluate kajongg.csv"""
    allRows = list(csv.reader(open('kajongg.csv','r'), delimiter=';'))
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
    print '{:<20} {:>5} {:>4}'.format('AI variant', 'games', 'won')
    for aiVariant, rows in games.items():
        print '{:<20}'.format(aiVariant[:20]),
        won = sum(int(x[-1]) for x in rows if x[1] in commonSeeds)
        print '{:>5} {:>4}%'.format(len(commonSeeds), str(100.0 * float(won) / len(commonSeeds))[:4]),
        if len(rows) > len(commonSeeds):
            won = sum(int(x[-1]) for x in rows)
            print '  total of {} games: {:>4}% won'.format(len(rows), str(100.0 * float(won) / len(rows))[:4]),
        print

def main():
    """parse options, play, evaluate results"""
    evaluate()
    print
    parser = OptionParser()
    parser.add_option('', '--gui', dest='gui', action='store_true',
        default=False, help='show graphical user interface')
    parser.add_option('', '--autoplay', dest='ruleset',
        default='Testset', help='play like a robot using RULESET',
        metavar='RULESET')
    parser.add_option('', '--ai', dest='ai',
        default='default', help='use AI variant',
        metavar='AI')
    parser.add_option('', '--seed', dest='seed',
        help='start first game with SEED, increment for following games',
        metavar='SEED', default=1)
    parser.add_option('', '--count', dest='count',
        help='play COUNT games',
        metavar='COUNT', default=0)
    parser.add_option('', '--showtraffic', dest='showtraffic', action='store_true',
        help='show network messages', default=False)
    parser.add_option('', '--showsql', dest='showsql', action='store_true',
        help='show database SQL commands', default=False)

    (options, args) = parser.parse_args()
    options.seed = int(options.seed)
    options.count = int(options.count)

    if args and ''.join(args):
        print 'unrecognized arguments:', ' '.join(args)
        sys.exit(2)

    try:
        for seed in range(options.seed, options.seed + options.count):
            print 'SEED=%d' % seed
            cmd = ['./kajongg.py --autoplay={} --seed={}'.format(options.ruleset, seed)]
            if not options.gui:
                cmd.append('--nogui')
            if options.ai:
                cmd.append('--ai=%s' % options.ai)
            if options.showtraffic:
                cmd.append('--showtraffic')
            if options.showsql:
                cmd.append('--showsql')
            cmd = ' '.join(cmd)
            print cmd
            process = subprocess.Popen(cmd, shell=True)
            _ = os.waitpid(process.pid, 0)[1]
    except KeyboardInterrupt:
        pass
    if options.count > 0:
        evaluate()


if __name__ == '__main__':
    main()
