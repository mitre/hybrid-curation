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
import json
import optparse
import itertools
import csv
import collections

######################################################################

"""
Merge annotations and document contents.

This script takes a list of docID-filename pairs, and a set of standoff annotations on the documents.
In addition to offsets, the annotations have semantic types and concept IDs.

The script merges all of the annotations for each document,
grouping them by type and concept. It also reads in the text of each document.

Finally, it produces a file with one JSON dictionary per line,
representing all of the annotation groups for a single document.

Each JSON dict looks like this:

{"docID"	: "Document ID string",
 "source"	: "Source file, if available",
 "content"	: "XML content of the document",
 "annotations" : [{"type" : "concept type",
    				"conceptID" : "from some ontology, etc",
                    "gloss" : "string",
                    "offsets" : [[start, end] ...],
                    },
                  ...]
}

(Note that the offset space includes any markup in the content.)
"""

######################################################################

idRE = re.compile("^[\w~@#%^*-+/]{1,80}$")	# Mild security measure: Precribed length and set of characters in IDs
def readDocs (docsFile):
    try:
        with file(docsFile, "rU") as f:
            n = 0
            for line in f:
                n += 1
                line = line.strip().split()
                try:
                    assert len(line) >= 2, "Short line"
                    id, docFile = line[:2]
                    assert idRE.match(id), "Bad ID format"
                    with open(docFile, "rU") as d:
                        yield dict(docID=id, source=docFile, content="".join(d))
                except Exception as e:
                    print >>sys.stderr, "Skipping %s line %d - %s" % (docsFile, n, e)
    except Exception:
        print >sys.stderr, "Error reading docs file %r" % docsFile
        raise

def readAnnotations (annFile):
    try:
        with file(annFile, "rU") as f:
            for ann in csv.DictReader(f, fieldnames="docID type start end conceptID content".split(),
                                    restkey="extra", dialect="excel-tab"):
                start, end = int(ann["start"]), int(ann["end"])
                assert 0 <= start <= end, "Bad offsets"
                ann["offsets"] = (start, end)
                yield ann
    except Exception:
        print >sys.stderr, "Error reading annotations file %r" % docsFile
        raise

def pickGloss (annotations):
    lower = lambda s: s.lower()
    glossGroups = sorted((a["content"] for a in annotations), key=lower)
    glossGroups = [list(group) for (key, group) in itertools.groupby(glossGroups, lower)]
    # Pick largest number of occurrences, then longest string
    groupLength, glossLength, gloss = max((len(group), len(group[0]), group[0]) for group in glossGroups)
    return gloss   
            
def mergeAnnotations (docs, allAnnotations, glosses=False):
    docMap = dict((doc["docID"], doc) for doc in docs)
    # annMap[(docID, conceptType, conceptID)] => [annotations ...]
    annMap = collections.defaultdict(list)
    # glosses = collections.defaultdict(lambda : collections.defaultdict(lambda : collections.defaultdict())
    # Group the annotations by (docID, type, conceptID)
    for a in allAnnotations:
        annMap[(a["docID"], a["type"], a["conceptID"])].append(a)
    for (docID, conceptType, conceptID), someAnnotations in annMap.iteritems():
        doc = docMap[docID]
        # Maybe docs should just be defaultdicts
        if not doc.has_key("annotations"):
            doc["annotations"] = list()
        annGroup = dict(type=conceptType,
                        conceptID=conceptID,
                        offsets=sorted(a["offsets"] for a in someAnnotations))
        if glosses:
            annGroup["gloss"] = pickGloss(someAnnotations)
        doc["annotations"].append(annGroup)                                       

def dumpAnnotations (out, docs):
    # Sort everything for stability
    docs.sort(key=lambda d: d["docID"])
    for doc in docs:
        doc["annotations"].sort(key=lambda a: (a["type"], a["conceptID"]))
    for d in docs:
        print >>out, json.dumps(d, sort_keys=True)

######################################################################

optparser = optparse.OptionParser()
optparser.set_usage("""Usage: %prog [options] [annfiles ...]""")

optparser.add_option("--docs", help="Tab-sep file of document IDs and filenames")
optparser.add_option("--glosses", action="store_true", help="Pick a representative string for each annotation group")

(options, annFiles) = optparser.parse_args()

assert options.docs, "--docs is required"
docs = list(readDocs(options.docs))
print >>sys.stderr, "Read %d documents" % len(docs)

assert annFiles, "No annotation files"
annotations = list(itertools.chain.from_iterable(readAnnotations(f) for f in annFiles))
print >>sys.stderr, "Read %d annotations" % len(annotations)

mergeAnnotations(docs, annotations, glosses=options.glosses)
dumpAnnotations(sys.stdout, docs)

######################################################################
