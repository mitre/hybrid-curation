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

$/ = "</list>";

while (<>) {

  # Deal with badly overlapping list elements and annotations by rearranging them

  # <LIST> <ITEM> <ANNOTATION> </ITEM> => <ANNOTATION> <LIST> <ITEM> </ITEM>
  s,(<list(?:\s[^>]*)?> [\s]*) (<item(?:\s[^>]*)?>) ([^<]*) (<annotation(?:\s[^>]*)?>) ([^<]*) (</item>),$4$1$2$3$5$6,gx;

  # <ITEM> </ANNOTATION> </ITEM> </LIST> => <ITEM> </ITEM> </LIST> </ANNOTATION>
  s,(<item(?:\s[^>]*)?>) ([^<]*) (</annotation>) ([^<]*) (<br[\s]*/>\s*)? (</item>\s*) (</list>),$1$2$4$5$6$7$3,gx;

  print;
}
 
