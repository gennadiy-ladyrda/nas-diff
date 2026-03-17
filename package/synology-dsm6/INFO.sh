#!/bin/bash

set -eu

. /pkgscripts-ng/include/pkg_util.sh

package="nas-diff"
version="${PKG_VERSION:-0.1.0-0008}"
displayname="NAS Diff"
displayname_rus="NAS Diff"
description="Find and safely clean duplicate photos on Synology NAS."
description_rus="Find and safely clean duplicate photos on Synology NAS."
maintainer="${PKG_MAINTAINER:-nas-diff}"
distributor="${PKG_DISTRIBUTOR:-nas-diff}"
thirdparty="yes"
support_center="https://github.com/SynologyOpenSource/pkgscripts-ng"
arch="${PKG_ARCH:-$(pkg_get_platform_family)}"
firmware="${PKG_DSM_FIRMWARE:-6.1-15217}"
adminprotocol="http"
adminport="${PKG_ADMIN_PORT:-15173}"
dsmuidir="ui"
dsmappname="SYNO.SDS.NASDiff.Application"
install_dep_packages="${PKG_INSTALL_DEP_PACKAGES:-Docker}"
support_move="yes"

[ "$(caller)" != "0 NULL" ] && return 0
pkg_dump_info
