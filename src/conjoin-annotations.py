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

import sys
import fileinput
import collections
import csv

"""
Read in tab-delimited annotations,
Merge all the ones in the same document by conjoining the concept IDs with a slash,
Write them back out.

The canonical example is a drug and its main ingredient,
which we want to treat as the same entity.
"""


fieldnames = "docID annotType start end concept mention".split()

def readAnnotations (input):
    return csv.DictReader(input, dialect=csv.excel_tab, fieldnames=fieldnames)

def rewriteItems (items, delimiter="/"):
    n = nMerged = 0
    items = list(items)
    doc2concept = collections.defaultdict(set)
    for item in items:
        doc2concept[item["docID"]].add(item["concept"])
    for docID, concepts in doc2concept.iteritems():
        n += 1
        if len(concepts) > 1:
            nMerged += 1
        doc2concept[docID] = delimiter.join(sorted(concepts))
    for item in items:
        item["concept"] = doc2concept[item["docID"]]
    print >>sys.stderr, "%d documents, %d with merged annotations" % (n, nMerged)
    return items

def writeAnnotations (output, items):
    for item in items:
        print >>output, "\t".join(item[f] for f in fieldnames)

writeAnnotations(sys.stdout, rewriteItems(readAnnotations(fileinput.input())))
        
