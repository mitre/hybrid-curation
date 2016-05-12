# Hybrid Curation

Tools to support MITRE's methodology for crowd-sourced curation.

This package is an initial attempt at distributing the scripts and
utilities used in MITRE's Hybrid Curation experiments on Amazon
Mechanical Turk.

The following are the main scripts MITRE has used for the hybrid
curation methodology. Each is briefly discussed in Appendix A of the
white paper.

	simple-merge.py 
	new-make-items.py 
	bundle-hits.py
	unbundle-hits.py
	naive-bayes.py
	simple-score.py

If you want to limit your HITs to those Turkers who have passed a
qualifier, these scripts may be useful. Note that upload.qual.py
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
