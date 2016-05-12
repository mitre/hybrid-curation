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
import json
import fileinput
import codecs
import optparse

"""
For some short labels, the drug name is not explicitly mentioned in the text
This script adds a span at the top for the name of the drug.

It reads the NCBI annotations file to map docIDs to drug names.
Then it reads any additional files or stdin, which are expected
to be in the generic JSON format for document annotations.
"""

######################################################################

def readJSON (input):
    return [json.loads(i) for i in input]

def writeJSON (output, items):
    for item in items:
        print >>output, json.dumps(item, sort_keys=True, ensure_ascii=True)

def readDrugMap (ncbiFile):
    # Ignore all but the first two columns of this data
    drugMap = {}
    try:
        with codecs.open(ncbiFile, "rU", "utf8") as f:
            for line in f:
                line = line.split("\t")
                docID, drugName = line[0], line[2]
                drugMap[docID] = drugName
    except:
        print >sys.stderr, "Error reading drug map file %r" % ncbiFile
        raise
    return drugMap

def addDrugTitles (items, drugMap, cssClass="drugtitle"):
    for item in items:
        drugName = drugMap.get(item["docID"])
        if drugName:
            item["content"] = (("""<h1 class="%s"><span class="drug">%s</span></h1>\n""" % (cssClass, drugName))
                                + item["content"])
        else:
            print >>sys.stderr, "No drug name found for doc %s" % item["docID"]

######################################################################

optparser = optparse.OptionParser()
optparser.set_usage("""Usage: %prog NCBIoffsetsFile [htmlItemsFile]""")

(options, args) = optparser.parse_args()
ncbiFile = args.pop(0)

drugMap = readDrugMap(ncbiFile)
items = readJSON(fileinput.input(args))

addDrugTitles(items, drugMap)

writeJSON(sys.stdout, items)

print >>sys.stderr, "Processed %d items" % len(items)
