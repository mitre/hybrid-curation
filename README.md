# Hybrid Curation

Tools to support MITRE's methodology for crowd-sourced curation.

This package is an initial distribution of the scripts and
utilities used in MITRE's Hybrid Curation experiments on Amazon
Mechanical Turk, as described in the following papers:

  https://database.oxfordjournals.org/content/2014/bau094.abstract
  https://database.oxfordjournals.org/content/2015/bav016.abstract

The following are the main scripts MITRE has used for the hybrid
curation methodology. Each is briefly discussed in Appendix A of the
white paper (also available separately in the [hybrid-curation/doc directory](https://github.com/mitre/hybrid-curation/blob/master/doc]).

	simple-merge.py 
	new-make-items.py 
	bundle-hits.py
	unbundle-hits.py
	naive-bayes.py
	simple-score.py

If you want to limit your HITs to those Turkers who have passed a
qualifier, these scripts may be useful. Note that upload-qual.py
requires the boto package to be installed.
	
	make-qual.py
	upload-qual.py

The following are various utilities for regularization and cleanup
of the data, as well as other tasks:

	add-drug-title.py
	conjoin-annotations.py
	gluehtml.py
	simple-html.py
	xml2htmlWrapper.py
	hack-bad-lists.pl
	hack-bad-xml.pl
