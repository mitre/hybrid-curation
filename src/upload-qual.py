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
import random
import optparse
import codecs
import re
import fileinput
import json

import boto
from boto.mturk.question import *
from boto.mturk.connection import *

######################################################################

"""Upload qualifier test to MTurk

Expects a file containing questions and answers, to be posted as a qualifier.
By default, this is a simple textual format with QA "chunks" separated by
blank lines.  The first chunk is directions and other front matter.
Subsequent chunks each specify a question with answers. First line of
a QA chunk is the question, subsequent lines are answers.  The first
answer is always the correct one (but they can be shuffled or sorted
if requested).

If the --front option is used to specify the front matter then the
first chunk is interpreted as the first queston.

An alternate and more flexible format is one question per line
expressed as a JSON dictionary:

{"question" :   "<HTML STRING>",
 "answers" :    [{"answer": "Yes"}, {"answer": "No", "score": 10}, {"answer": "Maybe"}]}

One line may instead be instructions, etc:

{"frontmatter": "<HTML STRING>"}

Note that the HTML allowed in qualifiers is of a very limited form,
with no scripting etc. allowed. See the MTurk documentation for details.

The other components of the qualifier (title, description, etc.) can
be set as options to this script."""

######################################################################

answerKeyWrapperXML = '''<AnswerKey xmlns="http://mechanicalturk.amazonaws.com/AWSMechanicalTurkDataSchemas/2005-10-01/AnswerKey.xsd">
    %(answerKeys)s
    <QualificationValueMapping>
    <PercentageMapping>
    <MaximumSummedScore>%(maxScore)d</MaximumSummedScore>
    </PercentageMapping>
    </QualificationValueMapping>
    </AnswerKey>
    '''

answerKeyXML = '''<Question><QuestionIdentifier>%(questionID)s</QuestionIdentifier>
        %(answerOptions)s
        </Question>'''

answerOptionXML = '''<AnswerOption><SelectionIdentifier>%(answerID)s</SelectionIdentifier>
        <AnswerScore>%(answerScore)d</AnswerScore>
        </AnswerOption>'''

def INT (x):
    return int(round(float(x)))

def constructQual (conn, questions,
                   title=None, front=None, back=None):
    """Build the XML that MTurk expects.

    questions is of the form:
    [{"question" : text,
      "score" : number
      "answers": [{"answer" : text,
                   "score" : number},
                   ...
                   ]},
     ... ]
     
     where score is optional"""            
    qStructs = [  Overview([FormattedContent(front or "<h1>%s</h1>" % (title or "Qualifier"))]), ]
    answerXMLs = []
    maxScore = 0
    for qID, q in enumerate(questions, 1):
        qText = q["question"]
        if q.has_key("score"):
            q["score"] = INT(q["score"])
        answers = q["answers"]
        for a in answers:
            if a.has_key("score"):
                a["score"] = INT(a["score"])
        answers = [(a, id) for (id, a) in list(enumerate(answers, 1))]
        # print >> sys.stderr, answers
        # print >>sys.stderr, answers
        qStructs.append(Question(str(qID), 
                                 QuestionContent([FormattedContent(qText)]),
                                 answer_spec=AnswerSpecification(SelectionAnswer(selections=[(a["answer"], id) for a, id in answers])),
                                 is_required=True))
        answerOptions = [answerOptionXML % { "answerID" : id, "answerScore" : a["score"]} for a, id in answers if a.has_key("score")]
        assert answerOptions
        answerXMLs.append(answerKeyXML % {"questionID" : qID, "answerOptions" : "\n".join(answerOptions)})
        # If the question doesn't indicate how many points it's worth, use the max answer score
        maxScore += q["score"] if q.has_key("score") else max(a.get("score", 0) for a, id in answers)
    # print >>sys.stderr, answerXMLs
    if back:
        qStructs.append(Overview([FormattedContent(back)]))
    qf = QuestionForm(qStructs)
    keyXML = answerKeyWrapperXML % {"answerKeys" : "\n".join(answerXMLs),
                                    "maxScore" : maxScore }
    # print >>sys.stderr, "=====\n".join(("", qf.get_as_xml(), keyXML, ""))
    return qf, keyXML

def findExisting (conn, name):
    # Turns out search is just a loose keyword search
    existing = conn.search_qualification_types(name)
    existing = [e for e in existing if e.Name.lower() == name.lower()]
    if existing and len(existing) == 1:
        # print >>sys.stderr, existing[0].__dict__
        existing = existing[0].QualificationTypeId
        print >>sys.stderr, "Found existing qual %s" % existing
        return existing

def postQual (conn, qualid, name, qObject, keyXML,
              description=None,
              duration=None, retake=0, verbose=0):
    """Post the qual to MTurk using boto"""
    duration = duration or 20*len(questions)
    description = description or name
    if qualid:
        return conn.update_qualification_type(qualid,
                                              description=description, status="Active",
                                              test=qObject, answer_key=keyXML,
                                              test_duration=duration,                                 
                                              retry_delay=retake)
    else:
        return conn.create_qualification_type(name, description, "Active",
                                              test=qObject, answer_key=keyXML,
                                              test_duration=duration,
                                              retry_delay=retake)

######################################################################
#
# Readers for the simple text format and JSON
# Both return the JSON format

paraRE = re.compile(r"\n{2,}", re.U)

def simpleReader (file, popFrontmatter=True):
    """Dumbest format ever:
    items separated by blank lines
    First item is directions and other frontmatter.
    Other items are question-answer groups
    first line of item is the question, rest are answers
    first answer is the correct one (but they'll be shuffled if requested)"""    
    # file = open(file, "r")
    text = "".join(file).strip()
    text = paraRE.split(text)
    front = text.pop(0) if popFrontmatter else ""
    questions = []
    for q in text:
        q = q.split("\n")
        q, answers = q[0], q[1:]
        # right, wrong = answers[0], answers[1:]
        answers = [{"answer" : a } for a in answers]
        answers[0]["score"] = 1
        questions.append({"question" : q, "answers" : answers})
    return questions, front

def jsonReader (file):
    front = None
    questions = []
    n = 0
    for line in file:
        n += 1
        try:
            line = json.loads(line)
        except:
            print >>sys.stderr, "********** Problem with line", n
            raise
        if line.has_key("frontmatter"):
            front = line["frontmatter"]
            del line["frontmatter"]
            if line:
                print >>sys.stderr, "Unrecognized elements of frontmatter line:", line
        elif line.has_key("question"):
            questions.append(line)
        else:
            print >>sys.stderr, "Unrecognized line:", line
    return questions, front

def orderAnswers (answers):
    """Sort alphabetically, except put YES and NO up front"""
    hardcodes = {"yes" : (1,), "no": (2,)}
    answers.sort(key=lambda a: hardcodes.get(a["answer"].lower()) or (3, a["answer"]))
    return answers

tagRE = re.compile(r"<[/]?[a-z][^>]*>", re.I)

def plaintextify (txt):
    txt = tagRE.sub("", txt)
    for e, r in [("&lt;", "<"), ("&gt;", ">"), ("&amp;", "&")]:
        txt = txt.replace(e, r)
    return txt    

def parseDuration (dur):
    """Parse expressions like 60s, 24h, 31d"""
    num = dur
    mult = 1
    if dur[-1].lower() in "smhdw":
        mult = dict(s=1, m=60, h=60*60, d=24*60*60, w=7*24*60*60)[dur[-1].lower()]
        num = dur[:-1]
    # print >>sys.stderr, "%r %r" % (num, mult)
    try:
        return int(float(num) * mult)
    except:
        print >>sys.stderr, "Probem with duration expression", dur
        raise

######################################################################

# Apparently unnecessary
proxy = None # "gatekeeper.mitre.org"
verbose = 0

optParser = optparse.OptionParser(usage="%prog [options] [QAFILE]", version="%prog 0.3")

optParser.add_option("-v", "--verbose", action="count", help="More verbose output (cumulative)")
optParser.add_option("--qualid", help="MTurk-internal identifier for qualifier")
optParser.add_option("--name", "--title", help="Qualifier title for Turkers' consumption")
optParser.add_option("--front", "--intro", metavar="FILE", help="Instructions, etc. for top of qual. Default is first paragraph of plaintxt QAFILE")
optParser.add_option("--back", "--outro", metavar="FILE", help="Final remarks for bottom of qual")
optParser.add_option("--description", metavar="TEXT", help="Brief description of qual.  Default is frontmatter, stripped of HTML")

optParser.add_option("--retake", "--retakedelay", metavar="DURATION", # default=24*60*60,
                     help="Allowed delay between retakes of the test, e.g. 15m, 12h (default 1d)")
optParser.add_option("--duration", metavar="DURATION", default="1h",
                     help="Allowed time to take the test (default %default)")
optParser.add_option("--accesskey", "--access", metavar="KEY", help="AWS access key (default from ~/.boto)")
optParser.add_option("--secretkey", "--secret", metavar="KEY", help="AWS secret key (default from ~/.boto)")
optParser.add_option("--sandbox", action="store_true", help="Create qual on sandbox site")

optParser.add_option("--answershuffle", action="store_true", help="Shuffle answers")
optParser.add_option("--questionshuffle", action="store_true", help="Shuffle questions")
optParser.add_option("--answersort", "--sort", action="store_true", help="""Sort answers (with magic for Yes/No)""")
optParser.add_option("--json", action="store_true", help="QAFILE is JSON rather than simple QA format")

options, input = optParser.parse_args()
assert options.qualid or options.name
input = fileinput.input(input)
verbose = options.verbose

######################################################################

conn = boto.mturk.connection.MTurkConnection(aws_access_key_id=options.accesskey, 
                                             aws_secret_access_key=options.secretkey,
                                             proxy=proxy, proxy_port=80,
                                             host=("mechanicalturk.sandbox.amazonaws.com"
                                                   if options.sandbox
                                                   else None),
                                             debug=verbose
                                             )

# This is mostly as a proof of connection
if verbose:
    balance = conn.get_account_balance()[0]
    print >>sys.stderr, "===== Account balance:", balance

if options.json:
    questions, frontMatter = jsonReader(input)
else:
    questions, frontMatter = simpleReader(input, not options.front)
if options.front:
    if frontMatter:
        print >>sys.stderr, "Discarding frontmatter from QA file"
    with open(options.front) as f:
        frontMatter = "".join(f)

if options.questionshuffle:
    print >>sys.stderr, "Shuffling QUESTIONS ..."
    random.shuffle(questions)

if options.answershuffle:
    print >>sys.stderr, "Shuffling answers ..."
    for q in questions:
        random.shuffle(q["answers"])
elif options.answersort:
    print >>sys.stderr, "Sorting answers ..."
    for q in questions:
        q["answers"] = orderAnswers(q["answers"])

description = options.description or frontMatter and plaintextify(frontMatter) or options.name

if options.back:
    with open(options.back) as f:
        backMatter = "".join(f)
else:
    backMatter = None

# print >>sys.stderr, description

if verbose:
    print >>sys.stderr, "Read %d questions" % len(questions)
    # print >>sys.stderr, "Questions:", questions[:2] # [q.encode("utf8") for q in questions[:2]]

questions, key = constructQual(conn, questions,
                               title=options.name,
                               front=frontMatter,
                               back=backMatter)

if verbose > 1:
    print >>sys.stderr, questions, "(%d)" % len(questions)
    print >>sys.stderr, key

duration = parseDuration(options.duration)

if options.retake:
    retake = parseDuration(options.retake)
elif options.sandbox:
    retake = 0  # Better for debugging
else:
    retake = 24*60*60

if verbose:
    print >>sys.stderr, "Duration is %s, retake is %s" % (duration, retake)

qualid = options.qualid or findExisting(conn, options.name)
qual = postQual(conn, qualid, options.name, questions, key,
                description=description,
                duration=duration,
                retake=retake,
                verbose=verbose)

print >>sys.stderr, "%s qual %s %s" % ("Updated" if qualid else "Created",
                                       qual[0].QualificationTypeId,
                                       "(on the sandbox)" if options.sandbox else "(on the live site)")

######################################################################




