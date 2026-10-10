# How Fedora COPR turns this repository into a source RPM, when a COPR
# package's source type is "SCM" with the "make srpm" method: COPR runs
#
#     make -f .copr/Makefile srpm outdir=<dir> spec=<path to the spec>
#
# in a fresh checkout, as root in a minimal build root -- hence installing
# the two tools it needs first. See docs/installation.md.
spec ?= markdown-cornell-notes.spec
outdir ?= .

srpm:
	dnf -y install git-core rpm-build
	set -e; \
	name=markdown-cornell-notes; \
	version=$$(sed -n 's/^Version: *//p' $(spec)); \
	top=$$(mktemp -d); \
	mkdir -p $$top/SOURCES; \
	git config --global --add safe.directory "$$(pwd)"; \
	git archive --format=tar.gz --prefix=$$name-$$version/ -o $$top/SOURCES/$$name-$$version.tar.gz HEAD; \
	rpmbuild --define "_topdir $$top" --define "_srcrpmdir $(outdir)" -bs $(spec)

.PHONY: srpm
