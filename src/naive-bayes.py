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
import re
import csv
import optparse
import sys, warnings, types, time
import fileinput
import collections
import json
import string
# import sqlite3
import math

"""
An aggregator for multiple Turker responses that uses Naive Bayes.

The main inputs are the Turker responses in JSON format, and a key file
indicating the correct answers for some of the items. These are used to
compute Bayes factors for each Turker, which are in turn used to compute
a score for each candidate answer.

The result is a stripped-down version of the JSON format of the input.

Currently only works for boolean tasks.
"""

######################################################################
#
# Configury

progName = "naive-bayes"	        # To be filled in
startTime = time.time()

######################################################################
#
# Utilities

def help ():
    print "%s: no help yet" % (progName, )

def warn (string, warnClass=None, level=0):
    warnings.warn("%s: %s" % (progName, string), warnClass, level)

def maybeOpen (file, mode="r", encoding="utf8"):
    if type(file) is types.StringType:
        file = open(file, mode)
    if encoding:
        file = (mode == "r" and codecs.getreader or codecs.getwriter)(encoding)(file)
        # print >>sys.stderr, "maybeOpen", file, encoding
    return file

def readJSON (file):
    for line in maybeOpen(file, encoding=None):
        yield json.loads(line)

def writeJSON (file, source):
    for item in source:
        print >>file, json.dumps(item, sort_keys=False)

def logistic (x):
    return 1.0 / (1.0 + math.exp(-x))

######################################################################
#
# Readers

def readList (file):
    s = []
    with open(file) as f:
        for line in f:
            line = line.split()
            s.append(line[0])
    return s                

def readKeys (file, yes="yes"):
    keys = {}
    nTotal = nKept = 0
    for item in csv.DictReader(maybeOpen(file, "r", None), dialect="excel-tab", fieldnames="itemID label".split()):
        # assert item["label"] in ("yes", "no")
        if keys.get(item["itemID"], None) is not None:
            print >>sys.stderr, "Duplicate entries in key for", item["itemID"]
        k = item["label"].lower()
        k = normalizeAnswer(k, yes=yes)
        keys[item["itemID"]] = k
    return keys

def normalizeAnswer (answer, yes=None, missing=None):
    """Special-case hackery, perhaps eventually more parameterized ..."""
    if answer in (None, ""):
        answer = missing
    # Special-case hackery ...
    elif answer.lower() == yes:
        answer = "yes"
    else:
        answer = "no"
    return answer

def readResponses (file, itemref, answerref, yes="yes", missing=None):
    """Group responses by itemID"""
    responses = []
    n = 0
    for response in readJSON(file):
        n += 1
        # print  >>sys.stderr, n, r
        r = normalizeAnswer(response[answerref], yes=yes, missing=missing)
        responses.append((response["WorkerId"], response[itemref], r))
    return responses

######################################################################
#
# Processing

def countCoocurrences (reference, responses):
    counts = collections.defaultdict(lambda : collections.defaultdict(int))
    for workerID, itemID, answer in responses:
        if reference.has_key(itemID):
            ref = reference[itemID]
            counts[workerID][(answer, ref)] += 1
    return counts

class logOddsNB:

    def __init__ (self, references, responses):
        self.bayesFactors = self.computeBayesFactors(countCoocurrences(keys, responses))

    def computeBayesFactors (self, workerCounts):
        factors = {}
        for workerID, counts in workerCounts.iteritems():
            # Contingency table
            a, b, c, d = (counts[("yes", "yes")], counts[("yes", "no")],
                          counts[("no", "yes")], counts[("no", "no")])
            # Simplistic additive smoothing
            a += 1.0
            b += 1.0
            c += 1.0
            d += 1.0
            factorYes = ((a / (a + c)) / (b / (b + d)))
            factorNo = ((c / (a + c)) / (d / (b + d)))
            factors[workerID] = dict(yes=math.log(factorYes), no=math.log(factorNo))
        return factors

    def aggregateResponses (self, allResponses, logPrior=0.0):
        bayesFactors = self.bayesFactors
        nMissing = 0
        scores = collections.defaultdict(lambda: logPrior)
        for workerID, itemID, response in allResponses:
            if bayesFactors.has_key(workerID):
                factor = bayesFactors[workerID].get(response)
                if factor is not None:
                    scores[itemID] += factor
                    continue
            print >>sys.stderr, "Missing factor for worker/response %s/%s" % (workerID, response)
            nMissing += 1
        print >>sys.stderr, "%d responses ignored for lack of Bayes factors" % nMissing
        aggregate = []
        for itemID, score in scores.iteritems():
            aggregate.append((itemID,
                              "yes" if score > 0 else "no",
                              logistic(score)))                   
        return aggregate    
        
######################################################################
#
# Options

optparser = optparse.OptionParser(usage="%prog [options] JSON-RESPONSE-FILES ...")

optparser.add_option("-v", "--verbose", action="count", help = "More verbose output")
# optParser.add_option("--replace", action="store_true", help = "Replace existing table")
# optParser.add_option("--table", default="bayesFactors", help="Table to create")
# optParser.add_option("--responses", default="responses", help="Response table to use")
# optParser.add_option("--references", default="referenceAnswers", help="Reference table to use")

optparser.add_option("-k", "--key", help="tab-delim key file", metavar="TSVFILE")
optparser.add_option("--itemids", help="Item IDs to include (all by default)", metavar="FLATFILE")
# optparser.add_option("--meta", help="Meta-annotation batch", metavar="JSONFILE")
# Is this necessary, given KEYS?
optparser.add_option("--controls", help="File of item IDs to use as controls, default uses --key", metavar="FLATFILE")
optparser.add_option("--itemref", metavar="NAME", default="Input.itemID", help="Use NAME for item ID identifier (default %default)")
optparser.add_option("--answerref", metavar="NAME", default="Answer.answer", help="Use NAME for answer identifier (default %default)")
optparser.add_option("--yes", metavar="VALUE", default="yes",
                     help='''Interpret VALUE as "yes" label, all others as "no" (default %default)''')
optparser.add_option("--missing", metavar="VALUE", default=None, help="Use VALUE for missing answers (default is to skip them)")
optparser.add_option("--logprior", metavar="LOGIT",type=float, default=0.0, help="Use LOGIT as the prior in the Naive Bayes summation (default %default))")

# optParser.add_option("--db", help = "Database file")

(options, files) = optparser.parse_args()

######################################################################
#
# Main

if options.key:
    keys = readKeys(options.key, yes=options.yes)
    print >>sys.stderr, '''Read %d keys (%d "yes")''' % (len(keys), sum(1 for k in keys.itervalues() if k == "yes"))
else:
    keys = {}

if options.controls:
    controlIDs = set(readList(options.controls))
    print >>sys.stderr, "Read %d control IDs" % len(controlIDs)
    if controlIDs.isdisjoint(keys):
        print >>sys.stderr, "***** No supervision for controls"
elif keys:
    controlIDs = set(keys)
else:
    controlIDs = set()

if options.itemids:
    itemIDs = set(readList(options.itemids))
    print >>sys.stderr, "Restricting to %d item IDs" % len(itemIDs)
    assert(itemIDs)
else:
    itemIDs = set()

responses = readResponses(fileinput.input(files), options.itemref, options.answerref, yes=options.yes, missing=options.missing)
print >>sys.stderr, '''Read %d responses (%d items, %d "yes", %d empty)''' % (len(responses), len(set(i for (w, i, r) in responses)),
                                                                              sum(1 for (w, i, r) in responses if r =="yes"),
                                                                              sum(1 for (w, i, r) in responses if r == None))

nb = logOddsNB(keys, responses)
nbAggregate = nb.aggregateResponses(responses, logPrior=options.logprior)
for itemID, answer, score in nbAggregate:
    print >>sys.stdout, json.dumps({"WorkerId": "NaiveBayes", options.itemref: itemID,
                                    options.answerref: answer, "Answer.score": score},
                                   sort_keys=True)

######################################################################
