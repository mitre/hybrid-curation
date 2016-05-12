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
import re
import optparse
import xml.etree.ElementTree as ET

"""
A very simple approach to rewriting arbitrary XML into HTML

By default, all XML elements are replaced by HTML <div> or <span> elements -
we use some simple heuristics based on newlines to determine which.
The XML tag name becomes the class= attribute of the new HTML element.
In this way, you can use CSS to style the new elements based on the old tags.

You can override the default behavior on a case-by-case basis via the options.
"""

######################################################################

# htmlMap = {"para" : "p",}

spanStartRE = re.compile("^\s*\n")

listTags = "ul ol".split()
divTags = listTags + "div p".split()

strippedMap = {}
def stripNS (tag):
    newTag = strippedMap.get(tag)
    if not newTag:
        if tag.startswith("{"):
            ns, newTag = tag.split("}", 1)
        strippedMap[tag] = newTag
    return newTag

# No longer special-casing this
# def handleAnnotation (old, new):
#     new.tag = "span"
#     new.set("class", old.get("diseaseConcept"))
#     handleChildren(old, new)
    
def handleList (old, new):
    for child in old:
        mapElements(child, new)
    for child in new:
        child.tag = "li"

def handleChildren (old, new):
    childHead = new.text
    for child in old:
        mapElements(child, new, head=childHead)
        childHead = child.tail                    

######################################################################
        
# These are set below from options
classAttrs = []
tagMap = {}

def mapElements (old, newParent, head=None, depth=0):
    """Builds a parallel XML structure, mapping to a few HTML types"""
    # print >>sys.stderr, " " * depth, parent, parent.text.replace("\n", r"\n") if parent.text != None else None
    new = ET.Element("") # old.attrib
    new.text = old.text
    new.tail = old.tail
    if newParent is not None:
        newParent.append(new)
    
    oldTag = stripNS(old.tag)
    newTag = tagMap.get(oldTag) or ""

    # Check for some special cases and let them manage their own recursion
    
    # No longer special-casing this
    # if newTag == "annotation":
    #     handleAnnotation(old, new)
    # elif
    if newTag in listTags:
        handleList(old, new)
    else:
        handleChildren(old, new)

    # Set the tag if we can
    if newTag and not new.tag:
        new.tag = newTag

    # Set the class= attribute
    for a in classAttrs:
        if old.get(a):
            new.set("class", old.get(a))
            break
    else:
        if new.tag == oldTag:	# Special case, mostly for <br/>
            pass
        else:
            new.set("class", oldTag)

    # Last chance to set the tag
    if new.tag:
        pass
    elif any(c.tag in divTags for c in new):
        new.tag = "div"
    elif head is None or new.tail is None:
        new.tag = "span"
    elif endsWithNewlineRE.search(head) and startsWithNewlineRE.search(new.tail):
        new.tag = "div"
    else:
        new.tag = "span"

    # if oldTag =="annotation":
    #     print >>sys.stderr, "%s => %s" % (oldTag, newTag)

    return new

endsWithNewlineRE = re.compile(r"\n\s*$")
startsWithNewlineRE = re.compile(r"^\s*\n")

######################################################################

optparser = optparse.OptionParser()
optparser.set_usage("""Usage: %prog [options] [xmlfile]""")

optparser.add_option("--map", default=[], nargs=2, action="append", metavar="OLD NEW",
                     help="Transform OLD to NEW tags, rather than DIV or SPAN (multiple)")
optparser.add_option("--class", default=[], dest="klass", action="append", metavar="ATTR",
                     help="Use value of ATTR= in old tag for class= attribute in new, rather than old tag name (multiple)")

(options, args) = optparser.parse_args()

tagMap = dict(options.map)
# print >>sys.stderr, tagMap
classAttrs = options.klass
 
# tree = xml.etree.ElementTree.ElementTree()
try:
    tree = ET.fromstring("".join(fileinput.input(args)))
except ET.ParseError as e:
    print >>sys.stderr, "Parse error on %s (%s)" % (" ".join(args) or "<STDIN>", e)
    raise
    
new = mapElements(tree, None)
ET.ElementTree(new).write(sys.stdout, encoding="utf-8",
                          # Avoids empty <div /> elements
                          method='html')

######################################################################
