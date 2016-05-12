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

import re
import sys
import fileinput

# An improved version of this might use the "W3C Suggestion" for HTML imports:
# http://www.w3.org/TR/html-imports/

includeRE = re.compile("\s*<include>([^<]+)</include>\s*", re.I)

def processFile (input, output):
    for line in input:
        m = includeRE.search(line)
        if m:
            filename = m.group(1)
            start, end = m.span()
            output.write(line[0:start])
            # These comments get interpreted badly in CSS sections ):
            # output.write("\n<!-- Begin inclusion from %s: -->\n" % filename)
            with open(filename) as f:
                processFile(f, output)
            # output.write("\n<!-- End inclusion from %s -->\n" % filename)
            output.write(line[end:])
        else:
            output.write(line)

processFile(fileinput.input(), sys.stdout)
