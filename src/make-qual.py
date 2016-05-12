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
import optparse
import cgi
import glob
import os.path
import random

"""
Convert simple tab-sep format for items into the JSON format that upload-qual.py understands

Assumes that the text of each prescription label will have been uploaded to a specified S3 bucket,
and constructs a "question" for each that is mostly just an <IFRAME> pointing to the corresponding URL.
"""

######################################################################

# Copied this from xml wrapper, need a shared module I suppose

def makeFilename (dir, base, extension):
    """Generalize this to other troublesome characters"""
    return os.path.join(dir, ("%s.%s" % (base, extension))).replace(";", "_")

def readAnswers (filename):
    """Reads tab-sep format"""
    answers = []
    n = 0
    with open(filename, "rU") as f:
        for line in f:
            n += 1
            try:
                sequence, code, text = line.strip().split(None, 2)
                sequence = int(sequence)
                answers.append((sequence, code.strip(), text.strip()))
            except Exception as e:
                print >>sys.stderr, "Problem with line %d - %s" % (n, e)
                raise
    return answers        
   
def readItems (input):
    fields = "qID fileID CUI answer".split()
    n = 0
    for line in fileinput.input(input):
        n += 1
        try:
            comment = line.find("#")
            if comment > -1:
                line = line[:comment]
            line = line.strip()
            if line:
                line = line.split()
                if len(line) != 4:
                    print >>sys.stderr, '''Skipping line %d - "%s ..."''' % (n, " ".join(line)[:30])
                else:
                    yield dict(zip(fields, line))
        except:
            print >>sys.stderr, "Error reading line %d of %s" % (n, input)
            raise

def iframe (bucket, filename, height=300, width="90%"):
    """Construct HTML for enclosing IFRAME"""
    filename = os.path.basename(filename)
    return ('''<iframe src="%s/%s" scrolling="yes" width="%s" height="%s">
			Your browser does not support IFRAMEs - very sorry!
            </iframe>'''
            % (bucket, filename, width, height))
        
def addQuestions (items, question, localdir, bucket):
    for item in items:
        fileGlob = makeFilename(localdir, "%s-%s-*" % (item["fileID"], item["CUI"]), "html")
        files = glob.glob(fileGlob)
        if len(files) == 1:
            item["filename"] = os.path.basename(files[0])
            item["question"] = "%s\n%s" % (iframe(bucket, item["filename"]), question)
        else:
            print >>sys.stderr, "Cannot find unique file for %s" % fileGlob
    return items

def addAnswers (items, allAnswers):
    """Add all possible answers to each question, with only one of them associated with any credit"""
    allAnswers = sorted(allAnswers)
    for item in items:
        item["answers"] = [dict(answer="%s. %s" % (seq, text), score=(10 if item["answer"] == code else 0))
                            for (seq, code, text) in allAnswers]
    return items

######################################################################

optparser = optparse.OptionParser(usage="%prog [options] itemfile")

optparser.add_option("-v", "--verbose", action = "count", help="More verbose output")
# optparser.add_option("--items", metavar="FILE", help="Tab-delim key file")
# optparser.add_option("--front", metavar="HTMLFILE", help="Instructions, etc., for the top of the qual")
optparser.add_option("--dir", metavar="DIR", help="Directory containing the HTML text of the items")
optparser.add_option("--bucket", metavar="BUCKET", help="URL where the files in DIR will be")
optparser.add_option("--question", metavar="FILE", help="Question text, in XHTML 1999")
optparser.add_option("--answers", metavar="FILE", help="Answers, one per line as ID<TAB>TEXT")

# optparser.add_option("--survey", metavar="FILE", help="One survey question with answers on subsequent lines")
# optparser.add_option("--items", metavar="FILE", help="JSON items file")

(options, itemfiles) = optparser.parse_args()

# itemIDs = None
# if options.itemids:
#     with open(options.itemids) as f:
#         itemIDs = set(line.strip().split()[0] for line in f)
#     print >>sys.stderr,  itemIDs
# docIDs = set(itemID.split("-")[0] for itemID in itemIDs)
# # Maybe make these options eventually
# mutationColor = "#EE88BB"
# geneColor = "#AADD44"

######################################################################

if options.question:
    with open(options.question) as f:
        question = "".join(f)
else:
    question = ""
    print >>sys.stderr, "--question not provided"
    
assert options.answers
allAnswers = readAnswers(options.answers)

items = list(readItems(itemfiles))
# print >>sys.stderr, str(items)[:40], "..."

addQuestions(items, question, options.dir, options.bucket)
addAnswers(items, allAnswers)

random.shuffle(items)
for i in items:
    print json.dumps(i)

if options.verbose:
    print >>sys.stderr, "*** These files must be uploaded to here: %s ***" % (options.bucket or "<NO BUCKET!!!>")
    print >>sys.stderr, " ".join(i.get("filename", "<MISSING>") for i in items)
        
######################################################################
