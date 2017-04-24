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
import sys
import re
import codecs
import types
import csv
import sqlite3
import json
import collections
import fileinput

"""
Score Turker responses against an answer key.

Computes simple accuracy, as well as precision, recall and F-measure.
Displays some other summary statistics like abstentions and
average duration.

Can also produce simplistic raw interannotator scores.
"""

######################################################################
#
# Readers

def readReferences (filename):
    references = {}
    nIgnored = 0
    try:
        i = 0
        with open(filename, "rU") as f:
            for i, line in enumerate(f):
                line = line.strip()
                line = line.split()
                if len(line) > 1:
                    (id, answer) = line[0:2]
                    references[id] = answer
                else:
                    nIgnored += 1
    except Exception as e:
        print >>sys.stderr, "Error reading docs file %r, line %d" % (filename, i)
        raise
    if nIgnored:
        print >>sys.stderr, "Ignored %d odd (missing?) references" % nIgnored
    return references

# Why are these classes, could just be simple functions

class jsonResponseReader:

    def __init__ (self, file, itemRef="Input.itemID", answerRef="Answer.answer", abstain=None):
        self.itemRef = itemRef
        self.answerRef = answerRef
        self.abstain = abstain
        print >>sys.stderr, "%s: Reading from %s ..." % (self, file)
        self.file = file

    def __iter__ (self):
        n = 0
        for line in self.file:
            row = json.loads(line)
            row[self.answerRef] = row.get(self.answerRef) or self.abstain
            # Same as below - refactor if necessary
#             if not row.get("Input.itemID"):
#                 row["Input.itemID"] = row[self.itemRef]
#             if not row.get("Answer.answer"):
#                 row["Answer.answer"] = row.get(self.answerRef, None)
            yield row
            n += 1
        print >>sys.stderr, "%s: Read %d" % (self, n)            

class tabResponseReader:

    def __init__ (self, file, itemRef="Input.itemID", answerRef="Answer.answer", abstain=None):
        self.itemid = itemid
        self.answer = answer
        self.abstain = abstain
        print >>sys.stderr, "Reading from %s ..." % file
        self.csvReader = csv.DictReader(file, dialect=csv.excel_tab)

    def __iter__ (self):
        n = 0
        for row in self.csvReader:
            # print >>sys.stderr, self, row
            assert(not row.has_key("Answer.itemID") or (row["Input.itemID"] == row["Answer.itemID"]))
            for key, val in row.iteritems():
                try:
                    row[key] = val and val.decode("utf8") or None
                except UnicodeDecodeError, e:
                    print >>sys.stderr, '''%s: %s => \"%r"''' % (e, key, val)
            if not row.get("Input.itemID"):
                row["Input.itemID"] = row[self.itemid]
            if not row.get("Answer.answer"):
                row["Answer.answer"] = row.get(self.answer, None)
            row["Answer.answer"] = row["Answer.answer"] or self.abstain
            yield row
            n += 1
        print >>sys.stderr, "%s: %d" % (self, n)

######################################################################
#
# Scoring
import math

def median (data):
    if not data:
        return None
    data = sorted(data)
    # print data
    l = len(data)
    if l > 1 and l % 2:
        return (data[int(math.floor(l/2))] + data[int(math.ceil(l/2))]) / 2
    else:
        return data[int(l/2)]        

class simpleScorer:
    
    def __init__ (self, responses, itemRef="Input.itemID", answerRef="Answer.answer"):
        self.responses = list(responses)
        self.itemRef = itemRef
        self.answerRef = answerRef

    labelWidth = 40

    def scoreReference (self, references, smoothing=0.5, prAnswers=set()):
        itemRef = self.itemRef
        answerRef = self.answerRef
        overall = collections.defaultdict(float)
        turkers = collections.defaultdict(lambda : collections.defaultdict(float))
        prAnswers = set(a.lower() for a in prAnswers)
        allDurations = []
        adjustedDurations = []

        for item in self.responses:
            itemID = item[itemRef]
            turkerID = item["WorkerId"]
            if itemID in references:
                overall["total"] += 1
                turkers[turkerID]["total"] += 1
                ref = references[itemID].lower()
                response = item[answerRef]
                # xprint >>sys.stderr, turkerID, response, ref
                if response is None:
                    turkers[turkerID]["abstentions"] += 1
                else:
                    response = response.lower()
                if ref == response:
                    overall["correct"] += 1
                    turkers[turkerID]["correct"] += 1
                if ref in prAnswers:
                    overall["recallDenominator"] += 1
                    turkers[turkerID]["recallDenominator"] += 1                
                if response in prAnswers:
                    turkers[turkerID]["precisionDenominator"] += 1        
                    overall["precisionDenominator"] += 1
                    if ref == response:
                        turkers[turkerID]["prNumerator"] += 1
                        overall["prNumerator"] += 1
            turkers[turkerID]["totalItems"] += 1
            dur = float(item["WorkTimeInSeconds"])
            aDur = item.get("AdjustedWorkTime", None)
            if aDur is not None:
                aDur = float(aDur)
                turkers[turkerID]["duration"] += aDur
                adjustedDurations.append(aDur)
            else:
                turkers[turkerID]["duration"] += dur
            allDurations.append(dur)

        if adjustedDurations:
            print >>sys.stderr, "Using adjusted HIT durations"
            if len(allDurations) != len(adjustedDurations):
                print >>sys.stderr, "***** Mix of raw and adjusted durations!!! *****"
                        
        for turkerID, scores in turkers.iteritems():
            scores["accuracy"] = (scores["correct"] + smoothing) / (scores["total"] + 1)
        print "======== Overall"
        print "%20s %4d" % ("Total Turkers", len(turkers))
        print "%20s %s" % ("Avg response", self.prettyPrint([(overall["correct"], overall["total"])])   )
        print "%20s %s" % ("Avg Turker", self.prettyPrint([(s["correct"], s["total"]) for s in turkers.itervalues()]))
        print "%20s %8.3f" % ("Median Turker",  median([s["correct"] / s["total"] for s in turkers.itervalues() if s["total"]]) or 0)
        print "%20s %s" % ("Avg Duration", self.prettyPrint([(s["duration"], s["totalItems"]) for s in turkers.itervalues()]))
        print "%20s %8.3f (of %d)" % ("Median Duration", median(adjustedDurations or allDurations), len(adjustedDurations or allDurations))
        # print "%20s %8.3f (of %d)" % ("Median Duration", median([s["duration"] / s["totalItems"] for s in turkers.itervalues() if s["total"]]), len(turkers))

        if prAnswers:
            print "%20s %s" % ("Avg Precision",
                               self.prettyPrint([(s["prNumerator"], s["precisionDenominator"]) for s in turkers.itervalues()]))
            print "%20s %s" % ("Avg Recall",
                               self.prettyPrint([(s["prNumerator"], s["recallDenominator"]) for s in turkers.itervalues()]))
            print "%20s %s" % ("Overall Precision",
                                self.prettyPrint([(overall["prNumerator"], overall["precisionDenominator"])])   )
            print "%20s %s" % ("Overall Recall",
                                self.prettyPrint([(overall["prNumerator"], overall["recallDenominator"])])   )

        print "%-20s  %-18s  %-18s  %-18s  %-9s  %-8s  %-8s" % ("======== Individual", "Smoothed accuracy", "Precision  ", "Recall  ", "F  ", "Duration", "Abstains")
        for turkerID in sorted(turkers, key=lambda t: (turkers[t]["accuracy"], turkers[t]["total"]), reverse=True):
            acc = self.prettyPrint([(turkers[turkerID]["correct"], turkers[turkerID]["total"])],
                                   turkers[turkerID]["accuracy"])
            if prAnswers:
                p = self.prettyPrint([(turkers[turkerID]["prNumerator"], turkers[turkerID]["precisionDenominator"])])
                r = self.prettyPrint([(turkers[turkerID]["prNumerator"], turkers[turkerID]["recallDenominator"])])
                if (turkers[turkerID]["precisionDenominator"] or turkers[turkerID]["recallDenominator"]):
                    f = "%8.3f " % (2*turkers[turkerID]["prNumerator"]
                                    / ((turkers[turkerID]["precisionDenominator"] + turkers[turkerID]["recallDenominator"])
                                        or 1))
                else:
                    f = "%9s" % ""
            else:
                p = r = f = ""
            dur = "%10.1f" % (turkers[turkerID]["duration"] / turkers[turkerID]["totalItems"])
            ab = ("%8.3f" % (turkers[turkerID]["abstentions"] / turkers[turkerID]["totalItems"])
                  if turkers[turkerID]["abstentions"] 
                  else " " * 8)
            print "%20s%s%s%s%s%s%s" % (turkerID, acc, p, r, f, dur, ab)

    # def report1 (self, label, ratios, figure=None):
    #     # Unused?
    #     """Ratios looks like [(num, denom) ...]"""
    #     w = self.labelWidth
    #     ratios = list(ratios)
    #     n = sum(1 for (num, denom) in ratios if denom > 0)
    #     if figure is None and n > 0:
    #         figure = sum(num/denom for (num, denom) in ratios if denom > 0) / n
    #     note = ""
    #     if len(ratios) == 1:
    #         note = "(%g / %g)" % ratios[0]
    #     elif len(ratios) > 1:
    #         note = "(avg of %d)" % n
    #     if n == 0 and figure is None:
    #         print "%*s%8s" % (w, label, "---")
    #     else:
    #         print "%*s%8.3f\t%s" % (w, label, figure, note)

    def prettyPrint (self, ratios, figure=None):
        """Produces an average of the inputs, with the numerator and denominator in parens
        Ratios looks like [(num, denom), ...]"""
        ratios = list(ratios)
        n = sum(1 for (num, denom) in ratios if denom > 0)
        if figure is None and n > 0:
            figure = sum(num/denom for (num, denom) in ratios if denom > 0) / n
        note = ""
        if len(ratios) == 1:
            note = "(%g / %g)" % ratios[0]
        elif len(ratios) > 1:
            note = "(avg of %d)" % n
        if n == 0:
            return "%8s %11s" % ("---", "")
        else:
            return "%8.3f %-11s" % (figure, note)

    def interannotator (self):
        itemRef = self.itemRef
        answerRef = self.answerRef
        item2responses = collections.defaultdict(dict)
        for item in self.responses:
            itemID = item[itemRef]
            turkerID = item["WorkerId"]
            response = item[answerRef]
            item2responses[itemID][turkerID] = response
        pairs = collections.defaultdict(lambda : collections.defaultdict(int))
        for responses in item2responses.itervalues():
            for turker1, response1 in responses.iteritems():
                for turker2, response2 in responses.iteritems():
                    if turker2 > turker1:
                        pairs[(turker1, turker2)]["total"] += 1
                        if response1 == response2:
                            pairs[(turker1, turker2)]["agreed"] += 1
        totalAgreement = 0
        print "\n========== Simple interannotator agreement"
        for pair, data in pairs.iteritems():
            print "%15s %-15s %s" % (pair[0], pair[1], self.prettyPrint([(data["agreed"], data["total"])]))
        print "%31s %s" % ("Average", self.prettyPrint([(d["agreed"], d["total"]) for d in pairs.itervalues()]))

# class dbWriter:

#     def __init__ (self, file, verbose=1):
#         self.conn = sqlite3.connect(file)
#         self.cursor = self.conn.cursor()
#         self.verbose = verbose

#     def loadResponses (self, responses):
#         for response in responses:
#             # print >>sys.stderr, response
#             row = [response[x] or None for x in "AssignmentId Input.itemID Answer.answer WorkerId WorkTimeInSeconds".split()]
#             # print >>sys.stderr, row
#             self.cursor.execute("""insert or ignore into responses (assignmentID, itemID, answer, workerID, workTime) values (?, ?,?,?,?)""", row)
                       
#     def loadQuestions (self, responses, cols):
#         cache = []
#         cols = cols.split()
#         for response in responses:
#             row = [response["Input.itemID"],
#                    response["HITId"],
#                    " - ".join([response.get(x, "?") for x in cols])]
#             if row not in cache:
#                 self.cursor.execute("""insert or ignore into questions (itemID, hitID, question) values (?,?,?)""", row)
#                 cache.append(row)

#     def loadReference (self, responses, refcol="Input.control_right"):
#         cache = []
#         for response in responses:
#             refdata = response.get(refcol, None) or response.get("Input." + refcol, None)
#             row = [response.get("Input.itemID", None), 
#                    response.get(refcol, None) or response.get("Input." + refcol, None),
#                    None        # Skip wrongAnswer stuff for now ...
#                    ]
#             if row not in cache:
#                 # print >>sys.stderr, row
#                 self.cursor.execute("""insert or ignore into referenceAnswers (itemID, rightAnswer, wrongAnswer) values (?,?,?)""", row)
#                 cache.append(row)

#     def loadPredicted (self, responses):
#         """Sadly specific to this HIT"""
#         cache = []
#         for response in responses:
#             scores = [(float(response["Input.score%d" % x]), x) for x in range(1, 4)]
#             scores.sort(reverse=True)
#             if scores[0][0] > scores[1][0]:
#                 vote = scores[0][1]
#             else:
#                 vote = None
#             row = [response["Input.itemID"], vote]
#             if row not in cache:
#                 self.cursor.execute("""insert into predictedAnswers (itemID, answer) values (?,?)""", row)
#                 cache.append(row)

#     def loadMajority (self, responses, threshold=3):
#         groups = {}
#         for response in responses:
#             itemID = response["Input.itemID"]
#             answer = response["Answer.answer"]
#             groups[itemID] = groups.get(itemID, {})
#             groups[itemID][answer] = groups[itemID].get(answer, 0) + 1
#         nLoaded = 0
#         for itemID, dist in groups.iteritems():
#             l = [(dist[answer], answer) for answer in dist] + [(0.0, None)]
#             l.sort(reverse=True)
#             # print >>sys.stderr, l
#             tots = sum([n for (n, answer) in l])
#             if tots >= threshold and l[0][0] > l[1][0]:
#                 answer = l[0][1]
#                 self.cursor.execute("""insert or ignore into majorityAnswers (itemID, answer, majority) values (?,?,?)""",
#                                     (itemID, answer, answer and (l[0][0]/tots) or None))
#                 nLoaded += 1
#         if self.verbose:
#             print >>sys.stderr, "%s: %d majority answers" % (self, nLoaded)

######################################################################
#
# Options

import optparse

optparser = optparse.OptionParser()

optparser.add_option("-v", "--verbose", dest="verbose", action = "count",
                  help = "More verbose output")
optparser.add_option("--references", metavar="FILE", help="Read reference answers from FILENAME in TSV format")
optparser.add_option("--tsv", action="store_true", help="Input lines are in tab-sep format")
optparser.add_option("--abstain", metavar="NOANSWER", default=None, help="Interpret no answer as NOANSWER")
optparser.add_option("--items", metavar="NAME", default="Input.itemID", help="Use NAME for item ID identifier (default %default)")
optparser.add_option("--answers", metavar="NAME", default="Answer.answer", help="Use NAME for answer identifier (default %default)")
optparser.add_option("--pr", metavar="ANSWERS", default="", help="""Report precision, recall, F-measure. ANSWERS is a list of "true" labels.""")
optparser.add_option("--inter", action="store_true", help="Report simple inter-annotator agreement")

# optparser.add_option("-o", "--output", dest="output", help="write HITs to FILE", metavar="FILE")
# optparser.add_option("--refcol", help="Load reference tables using COLNAME", metavar="COLNAME")
# optparser.add_option("--answercol", help="Use COLNAME as answer", metavar="COLNAME")
# optparser.add_option("--questioncols", "--questioncol", help="Append values of COLNAMES to represent question", metavar="COLNAMES")
# optparser.add_option("--db", help="Existing database to load into", metavar="DB")
# optparser.add_option("--majority", metavar="INT", help="Fill majorityAnswer table only for items with INT or more responses", default=3)

(options, infiles) = optparser.parse_args()
assert options.references, "--references argument required"

######################################################################
#
# Main

# print >>sys.stderr, infile
responses = (tabResponseReader if options.tsv 
             else jsonResponseReader)(fileinput.input(infiles),
                                      itemRef=options.items, answerRef=options.answers,
                                      abstain=options.abstain)
responses = list(responses)
references = readReferences(options.references)

scorer = simpleScorer(responses, itemRef=options.items, answerRef=options.answers)
scorer.scoreReference(references, prAnswers=set(options.pr.split()))
if options.inter:
    scorer.interannotator()

# loader = dbWriter(options.db)
# loader.loadQuestions(responses, options.questioncols)
# loader.loadResponses(responses)
# loader.loadPredicted(responses)
# loader.loadMajority(responses, threshold=int(options.majority))
# if options.refcol:
#     print >>sys.stderr, "Loading reference answers using %s column" % options.refcol
#     loader.loadReference(responses, options.refcol)
# loader.conn.commit()

######################################################################
