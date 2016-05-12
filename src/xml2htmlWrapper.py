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
import os, os.path
import errno
import optparse
import re
import codecs

"""
Some of our utilities work on files rather than the contents of JSON fields.

Using the -split option, this utility can be used to temporarily split the "content"
field of each JSON item out into a temporary file in a specified directory.

Then these files can be individually processed with whatever pipeline is appropriate.
(In particular we usually turn XML into HTML at this point.)

Finally -merge can be used to pull the processed versions of the files back into the JSON items.
"""

######################################################################

def makedirs (dir):
    try:
        os.makedirs(dir)
    except OSError as e: # Python >2.5
        if e.errno == errno.EEXIST and os.path.isdir(dir):
            pass
        else:
            raise

badCharRE = re.compile(r"[/;:]")
def makeFilename (dir, base, extension):
    """Use a standard filename for each item so it can be read back in later"""
    # Generalize this to other troublesome characters
    return os.path.join(dir, badCharRE.sub("_", "%s.%s" % (base, extension)))

def readItems (infile):
    with codecs.open(infile, "rU", "utf-8") as f:
        for line in f:
            # print >>sys.stderr, type(line)
            yield json.loads(line)

def writeItems (items, out):
    for i in items:
        try:
            print >>out, json.dumps(i, sort_keys=True, ensure_ascii=False)
        except Exception as e:
            print >>sys.stderr, "Error dumping item %s - %s" % (i["itemID"], e)
            raise
        
def writeTempFiles (items, dir):
    makedirs(dir)
    for i in items:
        with codecs.open(makeFilename(dir, i["itemID"], "xml"), "w", "utf-8") as f:
            f.write(i["content"])

def mergeTempFiles (items, dir):
    """Read in the post-processed file for each item"""
    nErrors = 0
    for i in items:
        try:
            filename = makeFilename(dir, i["itemID"], "html")
            with codecs.open(filename, "rU", "utf-8") as f:
                content = "".join(f)
                if content:
                    i["content"] = content
                    yield i
                else:
                    print >>sys.stderr, "Empty content for item %s (%s), skipping it" % (i["itemID"], filename)
                    nErrors += 1
        except IOError as e: # Python >2.5
            if e.errno == errno.ENOENT:
                nErrors += 1
                if nErrors < 5:
                    print >>sys.stderr, "Can't find %s, skipping ..." % (filename,)
            else:
                raise
    if nErrors:
        print >>sys.stderr, "%d problem files altogether" % nErrors


# Should remove this for generality - do it to the files if it's an issue
badTagRE = re.compile(r"\s*<[/]?(?:html|body)([^>])*>\s*", re.I | re.U)
def fixupHTML (items):
    for i in items:
        i["content"] = badTagRE.sub("", i["content"])
        yield i        

######################################################################

optparser = optparse.OptionParser()
optparser.set_usage("""Usage: %prog [options] itemfile tempdir""")

optparser.add_option("--split", action="store_true")
optparser.add_option("--merge", action="store_true")
# Which field should be an option
# optparser.add_option("--field", default="content" ...)

(options, args) = optparser.parse_args()

assert len(args) == 2
itemfile, tempdir = args

assert options.split or options.merge
assert not (options.split and options.merge)

if options.split:
    writeTempFiles(readItems(itemfile), tempdir)
elif options.merge:
    writeItems(fixupHTML(mergeTempFiles(readItems(itemfile), tempdir)),
               codecs.getwriter("utf-8")(sys.stdout))
