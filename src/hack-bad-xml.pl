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

# Clean up a number of issues with the Rx labels
# Makes some strong assumptions about that the XML is fairly simplistic

while (<>) {
  # Start or end tags for these are sometimes simply missing, so let's delete them everywhere
  s,<[/]?(excerpt|highlight|text|component|section)(?:\s[^>]*)?>,,g;

  # Several orphaned styling tags within titles, so let's sacrifice styling within titles (which we assume are single lines)
  s,<[/]?content(?:\s[^>]*)?>,,g if (m,<[/]?title>,);

  # Deal with badly overlapping styling elements and annotations by deleting the styling tags
  s,<content(?:\s[^>]*)?> ([^<]*) (<annotation(?:\s[^>]*)?>) ([^<]*) </content> ([^<]*) (</annotation>),$1$2$3$4$5,gx;
  s,(<annotation(?:\s[^>]*)?>) ([^<]*) <content(?:\s[^>]*)?> ([^<]*) (</annotation>) ([^<]*) </content>,$1$2$3$4$5,gx;

  # Ugh, some bad overlaps with footnotes, which would be badly rendered anyway, just turn them into parentheticals
  s,<footnote(?:\s[^>]*)?>, (,g;
  s,[.]?</footnote>,),g;

  print;
}
