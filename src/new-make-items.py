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
import optparse
import fileinput
import json
import itertools
import cgi
import collections

######################################################################

idRE = re.compile("^[\w~@#%^*-+/]{1,80}$")	# Mild security measure: Precribed length and set of characters in IDs
def readDocs (input):
    for line in input:
        doc = json.loads(line)
        assert idRE.match(doc["id"]), "Bad ID format"
        yield doc

def planMarkup (annotations, tag, attributes, skipEmpties=True):
    tagID = 0
    # print >>sys.stderr, annotations
    startTag = "<%s %s>" % (tag, " ".join('''%s="%s"''' % (k, cgi.escape(v, quote=True)) for k, v in attributes.iteritems()))
    endTag = "</%s>" % tag
    for s, e in annotations["offsets"]:
        tagID += 1 
        assert s <= e
        if s == e:
            if not skipEmpties:
                yield dict(pos=s, offsets=(s, e), key=(s, 0, -s), id=tagID, tag=startTag + endTag, type="empty")
        else:
            yield dict(pos=s, offsets=(s, e), key=(s, 2, -e), id=tagID, tag=startTag, type="start")
            yield dict(pos=e, offsets=(s, e), key=(e, 1, -s), id=tagID, tag=endTag, type="end")

def insertMarkup (content, markup):
    markup.sort(key=lambda d: d["key"])
    # print >>sys.stderr, markup
    result = ""
    pos = lastPos = 0
    tagStack = []
    for tag in markup:
        pos = tag["pos"]
        if tag["type"] == "end":
            assert tagStack, "Empty tag stack"
            if tagStack[-1]["id"] == tag["id"]:
                tagStack.pop()
            else:
                print >>sys.stderr, "***** Bad tag overlap at %s and %s" % (tagStack[-1]["offsets"], tag["offsets"])
                print >>sys.stderr, "\t%s\n\tvs. %s" % (tagStack[-1]["tag"], tag["tag"])
                print >>sys.stderr, "\tnear ...%s..." % (content[tagStack[-1]["offsets"][0] : tag["offsets"][1]])
        elif tag["type"] == "start":
            tagStack.append(tag)
        # print >>sys.stderr, content[lastPos:min(lastPos + 20,pos)], "\n"
        # print >>sys.stderr, tag["tag"], "\n"
        result += content[lastPos:pos]
        result += tag["tag"]
        lastPos = pos
    result += content[lastPos:]
    assert not tagStack
    return result

def generateItems (doc, conceptTypes):
    docID = doc["docID"]
    conceptGroups = collections.defaultdict(list)	# Partitioned by type
    for group in doc["annotations"]:
        conceptGroups[group["type"]].append(group)
    zeroConcepts = filter(lambda ct: not conceptGroups.get(ct), conceptTypes)
    if zeroConcepts:
        print >>sys.stderr, "No HITs for document %r: %s" % (docID, ", ".join("no %s annotations" % ct for ct in zeroConcepts))
        return
    # This is a list of n lists, where n is the number of concept types, in the same order as conceptTypes
    allTypeGroups = [conceptGroups[ct] for ct in conceptTypes]
    # print >>sys.stderr, allTypeGroups
    for tuple in itertools.product(*allTypeGroups):	# Cross-product
        # Each tuple has one concept group per type
        # print >>sys.stderr, tuple
        concepts = dict((group["type"], dict(conceptID=group["conceptID"], gloss=group.get("gloss")))
                        for group in tuple)
        itemID = "-".join([docID] + [group["conceptID"] for group in tuple])
        markup = list(itertools.chain.from_iterable(planMarkup(group, "annotation",
                                                               dict(conceptID=group["conceptID"],
                                                                    conceptType=group["type"]))
                                                    for group in tuple))
        # Have to deal with overlapping markup at some point
        yield dict(itemID=itemID, docID=docID, concepts=concepts,
                   content=insertMarkup(doc["content"], markup))

######################################################################

optparser = optparse.OptionParser()
optparser.set_usage("""Usage: %prog [options] [annfiles ...]""")

optparser.add_option("--concepts", metavar="CONCEPTLIST", help="Each item will be a tuple of these comcept types")

(options, docFiles) = optparser.parse_args()
assert docFiles

assert options.concepts
conceptTypes = options.concepts.split()

docs = readDocs(fileinput.input(docFiles))
items = list(itertools.chain.from_iterable(generateItems(d, conceptTypes) for d in docs))

for i in items:
    print >>sys.stdout, json.dumps(i, sort_keys=True)
