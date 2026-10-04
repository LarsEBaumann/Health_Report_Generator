# Explicit setup only. Runtime builds never install R dependencies.
bootstrap <- file.path(getwd(),'.r-bootstrap')
dir.create(bootstrap,showWarnings=FALSE)
.libPaths(c(bootstrap,.libPaths()))
if(!requireNamespace('renv',quietly=TRUE)) install.packages('renv',lib=bootstrap,repos='https://cloud.r-project.org')
lib <- file.path(getwd(),'.r-library')
dir.create(lib,showWarnings=FALSE)
renv::restore(lockfile='renv.lock',library=lib,prompt=FALSE)
