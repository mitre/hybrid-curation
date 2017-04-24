"""
Copyright 2015 The MITRE Corporation
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
   http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from __future__ import division
import warnings
import sys
import re
import codecs
import types
import random
import csv
import json
import itertools
import optparse
import cgi

"""
Reads HIT items and bundles them into fixed size HITs.
This is accomplished by appending sequential numerics onto the field names.

This can also inject control items at a specified rate, reusing them if necessary.
"""

######################################################################

def maybeOpen (file, mode="r", encoding="utf8"):
    if type(file) is types.StringType:
        file = open(file, mode)
    if encoding:
        file = (mode == "r" and codecs.getreader or codecs.getwriter)(encoding)(file)
        # print >>sys.stderr, "maybeOpen", file
    return file

######################################################################

class jsonItemReader:
    
    def __init__ (self, file):
        self.file = maybeOpen(file, "r", "utf8")
        
    def __iter__ (self):
        n = 1
        for line in self.file:
            try:
                item = json.loads(line)
                item["itemID"] = str(item["itemID"])
                yield item
            except ValueError, e:
                print >>sys.stderr, "********** Error on line %s line %d" % (file, n)
                print >>sys.stderr, line[:10], "...", line[-10:]
                raise
            n += 1

class tabItemReader:

    def __init__ (self, file):
        # print >>sys.stderr, "%s %s" % (self, file)
        self.file = maybeOpen(file, "r", None)
        # Why don't I use csv module???
        self.keys = self.file.next().strip().split("\t")
        
    def __iter__ (self):
        
        n = 0
        for line in self.file:
            # print >>sys.stderr, "Read:", line
            if not line:
                break
            n += 1
            yield dict(zip(self.keys, line.rstrip("\n").split("\t")))
        print >>sys.stderr, "Read %d from %s (%s) ..." % (n, self.file, self.keys)

def cleanValues (items):
    """CSV files for MTurk cannot have non-BMP characters, sigh
    Also decided to change newlines to spaces now"""
    nonBMPRE = re.compile(u"([^\u0000-\uFFFF]|[\uD800-\uDBFF][\uDC00-\uDFFF])+")
    for item in items:
        for (key, value) in item.iteritems():
            if isinstance(value, types.StringTypes):
                value = unicode(value)
                item[key] = nonBMPRE.sub(u"\uFFFD", value.replace("\n", " "))
                if False and value != item[key]:
                    print >>sys.stderr, ("Changed %s from\n%s to\n%s" % (key, value, item[key])).encode("utf8")     
        yield item

def writeBundles (outFile, items, keys=None, jsonize=(), htmlize=()):
    if not keys:
        items = list(items)
        keys = set()
        for item in items:
            keys = keys.union(item)
        keys = sorted(keys)

    writer = csv.DictWriter(maybeOpen(outFile, "w", None), keys)
    try:
        writer.writeheader()    # ARGH!
    except AttributeError:
        writer.writerow(dict(zip(keys, keys)))
    for bundle in items:
        for key, value in bundle.iteritems():
            if key in jsonize:
                bundle[key] = json.dumps(value, ensure_ascii=True, sort_keys=True)
            elif key in htmlize:
                bundle[key] = cgi.escape(value).replace("\n", " ").encode("ascii", "xmlcharrefreplace")
            else:
                bundle[key] = unicode(value).encode("utf8").replace("\n", " ")
        # print >>sys.stderr, bundle.keys()
        writer.writerow(bundle)

######################################################################
#
# Bundle

import math

class itemBundler:

    def __init__ (self, items, n, controlItems=[], controlRate=0.0, randomize=False, verbose=0, itemSuffix=True):
        # print >>sys.stderr, self
        if not itemSuffix:
            assert n == 1
        self.nBundle = n
        self.itemSuffix = itemSuffix
        self.verbose = verbose
        self.items = list(items)
        self.controls = list(controlItems)
        self.randomize = randomize
        if randomize:
            random.shuffle(self.items)
            random.shuffle(self.controls)
        self.controlRate = float(controlRate)
        self.adjustControlRate()
        assert 0.0 <= self.controlRate <= 1.0

    def adjustControlRate (self):
        """Play with the control rate so we don't end up with any partial bundles.
        This still isn't quite right, what we need to do is go to all integers,
        including total number of controls"""
        controlRate = self.controlRate
        if controlRate == 0:
            return
        testItems = len(self.items)
        bundleSize = self.nBundle
        totalBundles = testItems / ((1 - controlRate) * bundleSize)
        if abs(totalBundles - int(totalBundles)) > 0.001:
            if self.verbose > 1:
                print >>sys.stderr, "Expected number of bundles is fractional (%.3f)" % totalBundles
            totalBundles = math.ceil(totalBundles)
            totalItems = totalBundles * bundleSize
            controlItems = totalItems - testItems
            if self.verbose > 1:
                print >>sys.stderr, "Adjusting number of bundles to %.3f" % totalBundles
                print >>sys.stderr, "Adjusting number of total items to %d" % totalItems
                print >>sys.stderr, "Adjusting number of control items to %d" % controlItems
            controlRate = controlItems / totalItems
            print >>sys.stderr, "Adjusting control rate from %g to %.6f" % (self.controlRate, controlRate)
            self.controlRate = controlRate
        
    def bundle (self, bundleList):
        # if itemSuffix ...
        newBundle = {}
        for (i, item) in enumerate(bundleList):
            for (key, val) in item.iteritems():
                newBundle["%s_%d" % (key, i + 1)] = val
        return newBundle

    def __iter__ (self):
        # Fill bundle and add controls if ratio is insufficient ...
        # assert (1 - self.controlRate) * self.nBundle >= 1
        # assert (len(self.controls) / (len(self.controls) + len(self.items))) > self.controlRate

        bundleList = []
        controls = itertools.cycle(self.controls)       # Reuse controls if necessary
        controlRate = self.controlRate or 0.0
        # print >>sys.stderr, self.items
        items = list(self.items)
        nBundles = itemsUsed = controlsUsed = 0
        randomize = self.randomize and controlRate      # No need to randomize again if no control items - OVER-OPTIMIZATION?
        verbose = self.verbose

        while True:
            # We should really just explicitly build a full bundle each time through,
            # then we might not have to adjust the control rate explicitly ...
            if (itemsUsed + controlsUsed) and verbose > 1:
                print >>sys.stderr, "(%d / (%d + %d) = %.12f <?> %.12f" % (controlsUsed, itemsUsed, controlsUsed,
                                                                     (controlsUsed / (itemsUsed + controlsUsed)),
                                                                     controlRate)
            if controlsUsed < controlRate * (itemsUsed + controlsUsed) or not items:
                # Above SHOULD BE same as this: controlsUsed / (itemsUsed + controlsUsed) < controlRate
                bundleList.append(controls.next())
                controlsUsed += 1
            else:
                bundleList.append(items.pop())
                itemsUsed += 1
            if len(bundleList) == self.nBundle:
                if verbose > 2:
                    print >>sys.stderr, bundleList
                if randomize:
                    random.shuffle(bundleList)
                yield self.bundle(bundleList)
                nBundles += 1
                bundleList = []
                if not items:
                    break
        print >>sys.stderr, "Combined %d items with %d controls* into %d %d-bundles" % (itemsUsed, controlsUsed, nBundles, self.nBundle)
        assert not items
        assert not bundleList

def computeGoldRate (goldRate, n):
    """Rate can be specified as a fraction, or as the number of items per bundle"""
    if goldRate in (None, "1"):
        goldRate = 1.0 / n
    else:
        goldRate = float(goldRate)
        if goldRate >= 1.0:
            if goldRate >= n:
                warnings.warn("goldRate > n (%s > %d)" % (goldRate, n))
            goldRate = goldRate / n
    print >>sys.stderr, "Gold rate = %.2f" % goldRate
    return goldRate

import collections
def separateGold (allItems, goldIDs):
    """For when gold file just has itemID"""
    allItems = list(allItems)
    goldIDs = set(i.lower() for i in goldIDs)
    goldItems = []
    strawItems = []
    for item in allItems:
        if item["itemID"].lower() in goldIDs:
            item["isGold"] = 1         # add indicator
            goldItems.append(item)
        else:
            strawItems.append(item)
    print >>sys.stderr, "%d gold found, %d test items (%d)" % (len(goldItems), len(strawItems), len(allItems))
    # print >>sys.stderr, "Repeated gold: %s" % (list(i for i,c in collections.Counter(i["itemID"].lower() for i in goldItems).iteritems() if c > 1), )
    missingGold = goldIDs.difference([item["itemID"].lower() for item in goldItems])
    if missingGold:
        print >>sys.stderr, "%d gold IDs not found (e.g. %s)" % (len(missingGold), " ".join(list(missingGold)[:3]))
    return goldItems, strawItems    

######################################################################

optparser = optparse.OptionParser(usage="%prog [options] [infile]")

optparser.add_option("-v", "--verbose", dest="verbose", action = "count",
                  help = "More verbose output")
optparser.add_option("-n", help="Number of items per HIT", type="int", default=2)
optparser.add_option("-r", "--random", help="Randomize items across hits", action="store_true")
optparser.add_option("--gold", help="Gold-standard itemids", metavar="FILE")
optparser.add_option("--goldrate", help="How much gold to insert into each hit", metavar="NUMBER")
optparser.add_option("-o", "--output", help="write HITs to FILE", metavar="FILE")
optparser.add_option("--jsonize", default=[], action="append", metavar="FIELD", help="Encode each FIELD as JSON")
optparser.add_option("--htmlize", default=[], action="append", metavar="FIELD", help="Encode each FIELD using HTML numeric char refs")
optparser.add_option("-u", "--unique", action="store_true", default=False, help="Drop duplicate items")
optparser.add_option("--noclean", dest="clean", default=True, action="store_false", help="Do not clean values of newlines and non-BMP Unicode")

(options, args) = optparser.parse_args()
(infile, ) = args or (sys.stdin, )

# Eventually this will take options indicating tab vs. json, or it will just take json

items = list(jsonItemReader(infile))

def uniquify (items):
    seen = set()
    dropped = 0
    for item in items:
        id = item["itemID"]
        if id in seen:
            dropped += 1
            continue
        yield item
        seen.add(id)
    if dropped:
        print >>sys.stderr, "Dropped %d duplicate itemIDs" % dropped

if options.unique:
    items = list(uniquify(items))

if False and options.clean:
    items = cleanValues(items)

if options.gold:
    with open(options.gold) as f:
        itemIDs = set(i.split()[0] for i in f)
    gold, items = separateGold(items, itemIDs)
    if not options.random:
        print >>sys.stderr, "--random not specified, gold items will be in predictable positions"
    goldRate = computeGoldRate(options.goldrate, options.n)
else:
    gold = []
    goldRate = 0.0
    
bundler = itemBundler(items, options.n,
                      randomize=options.random,
                      controlItems=gold,
                      controlRate=goldRate,
                      verbose=options.verbose)

writeBundles(options.output or sys.stdout, bundler,
             jsonize=set("%s_%d" % combo for combo in itertools.product(options.jsonize, range(1, options.n + 1))),
             htmlize=set("%s_%d" % combo for combo in itertools.product(options.htmlize, range(1, options.n + 1))))

######################################################################
