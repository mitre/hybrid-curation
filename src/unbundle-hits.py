import sys
import re
import codecs
import types
import csv
import json
import optparse
import fileinput
import collections
import datetime
import time

"""
Essentially reverses the process of bundle-items.

Processes the CSV download from MTurk and bursts out multiple items in each HIT.
Each field name that ends in "_1", "_2" etc is assumed to be such a multiplexed field.
Any other fields will be repeated in the output.

Can produce JSON format rather than CSV if desired.
"""

csv.field_size_limit(10**6)

######################################################################

def maybeOpen (file, mode="r", encoding="utf8"):
    if type(file) is types.StringType:
        file = open(file, mode)
    if encoding:
        file = (mode == "r" and codecs.getreader or codecs.getwriter)(encoding)(file)
    return file

######################################################################

# class batchFileReader:

#     def __init__ (self, file):
#         self.csvReader = csv.DictReader(maybeOpen(file, "r", None))

#     wsRE = re.compile(r"\s") # re.U # NO!!!

#     def __iter__ (self):
#         n = 0
#         for row in self.csvReader:
#             n += 1
#             for key, old in row.items():
#                 if old:
#                     new = self.wsRE.sub(" ", row[key])
#                     if new is not old:
#                         row[key] = new      
#             yield row
#         # print >>sys.stderr, self, self.csvReader.fieldnames
#         print >>sys.stderr, "%s: %d" % (self, n)

wsRE = re.compile(r"\s") # re.U # NO!!!
def readBatchFile (input):
    n = 0
    for n, row in enumerate(csv.DictReader(input), 1):
        for key, old in row.items():
            if old:
                new = wsRE.sub(" ", row[key])
                if new is not old:
                    row[key] = new      
        yield row
    # print >>sys.stderr, self, self.csvReader.fieldnames
    print >>sys.stderr, "%d batch items read" % n

# class hitUnbundler:

#     def __init__ (self, source, burstplain=False, addSequenceID=False):
#         self.source = source
#         self.addSequenceID = addSequenceID
#         self.splitKeyRE = re.compile(burstplain and "^(.*[^0-9])([0-9]+)$" or "^(.+)_([0-9]+)$",
#                                      re.U | re.I)

def burstBundle (bundle, splitKeyRE):
        burst = {}      # Maps sequence number to attributes with that numeric suffix
        shared = {}     # Attributes without a numeric suffix
        for key in bundle:
            m = splitKeyRE.match(key)
            if m:
                newKey, index = m.groups()
                index = int(index)
                assert(index > 0)
                subBundle = burst.get(index, None)
                if not subBundle:
                    burst[index] = subBundle = {}
                subBundle[newKey] = bundle[key]
            else:
                shared[key] = bundle[key]
        return burst, shared

def unbundleHITs (source, burstplain=False, addSequenceID=False):
        splitKeyRE = re.compile(burstplain and "^(.*[^0-9])([0-9]+)$" or "^(.+)_([0-9]+)$",
                                     re.U | re.I)
        nIn = nOut = 0
#       indexCount = {}
        for bundle in source:
            nIn += 1
#           tempIndex = {}
#           for index in tempIndex:
#               indexCount[index] = indexCount.get(index, 0) + 1
            burst, shared = burstBundle(bundle, splitKeyRE)
            if addSequenceID:
                for index, subBundle in burst.iteritems():
                    subBundle["sequenceID"] = index
            for item in burst.values() or [{}]:
                # Add the shared ones back in to the burst items
                # print >>sys.stderr, "Burst item:", item
                for key in shared:
                    if item.has_key(key):
                        print >>sys.stderr, "Collision: %s=%s %s_n=%s" % (key, shared[key], key, item[key])
                    item[key] = shared[key]
                nOut += 1
                yield item
        print >>sys.stderr, "%s: %d => %d" % ("unbundle", nIn, nOut)

def adjustTimes (bundles):
    groups = collections.defaultdict(list)
    for b in bundles:
        # Clip out the timezone, which is not reliably parsed by strptime
        aTime, sTime = map(lambda t: time.mktime(datetime.datetime.strptime(t[:-8] + t[-5:], "%a %b %d %H:%M:%S %Y").timetuple()),
                           (b["AcceptTime"], b["SubmitTime"]))
        groups[b["WorkerId"]].append((sTime, aTime, b))
    origWorktime = adjustedWorktime = 0
    for workerID, bundles in groups.iteritems():
        lastSubmit = 0
        bundles.sort()
        for i, (sTime, aTime, b) in enumerate(bundles):
            b["AdjustedWorkTime"] = sTime - max(aTime, lastSubmit)
            assert b["AdjustedWorkTime"] >= 0
            # if b["AdjustedWorkTime"] == 0:
            #     print >>sys.stderr, "Zero work time!!! (%s %s), (%s %s)" % (bundles[i - 1][-1]["AcceptTime"], bundles[i - 1][-1]["SubmitTime"], b["AcceptTime"], b["SubmitTime"])
            lastSubmit = sTime
        
class tabItemWriter:

    def __init__ (self, file):
        self.file = maybeOpen(file, "w", None)
        # Hacky stuff to make some columns come first
        keyWeights = [(1, re.compile("^answer[.]", re.I | re.U)),
                      (2, re.compile("^input[.]", re.I | re.U)),
                      ]
        knowns = "itemID en fr1 score1 fr2 score2 fr3 score3 control_wrong control_right".split()
        for i in xrange(len(knowns)):
            keyWeights.append((100 + i, re.compile("^%s$" % knowns[i])))
        keyWeights.append((1000, None))
        self.keyWeights = keyWeights

    def sortKeys (self, keys):
        weightedKeys = []
        for key in keys:
            for weight, pattern in self.keyWeights:
                if not pattern or pattern.match(key):
                    weightedKeys.append((weight, key))
                    break
        keys = weightedKeys
        keys.sort()
        # keys.reverse()
        return [key for (weight, key) in keys]

    def writeAll (self, source):
        source = iter(source)
        firstItem = source.next()
        keys = self.sortKeys(firstItem.keys())
        print >>self.file, "\t".join(keys)
        for fake in ((firstItem, ), source):
            for item in fake:
                print >>self.file, "\t".join([str(item.get(key, "EMPTY")) for key in keys])

class jsonItemWriter:

    def __init__ (self, file):
        self.file = maybeOpen(file, "w", None)

    def writeAll (self, source):
        for item in source:
            print >>self.file, json.dumps(item, sort_keys=True)

######################################################################

optparser = optparse.OptionParser()

optparser.add_option("-v", "--verbose", dest="verbose", action = "count",
                  help = "More verbose output")
optparser.add_option("--plain", action="store_true",
                     help="Burst keys that end in digits; Default is to burst keys that end in underscore-digit")
optparser.add_option("--addseq", action="store_true", help="Add a sequence ID to the burst items")
optparser.add_option("--json", action="store_true",
                     help="Produce json output rather than tab-sep")

(options, args) = optparser.parse_args()

# (infile, ) = args or (None, )
# infile = infile in ("-", None) and sys.stdin or open(infile, "r")

bundles = list(readBatchFile(fileinput.input(args)))
adjustTimes(bundles)

print >>sys.stderr, "Average adjusted worktime %.1fs" % (sum(b["AdjustedWorkTime"] for b in bundles)/(len(bundles) or 1))

items = unbundleHITs(bundles, burstplain=options.plain, addSequenceID=options.addseq)
writer = (options.json and jsonItemWriter or tabItemWriter)(sys.stdout)
writer.writeAll(items)

######################################################################
