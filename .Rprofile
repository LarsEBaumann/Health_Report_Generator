# Use the isolated restored library, including renders executed in temporary folders.
project <- Sys.getenv('HEALTH_REPORT_PROJECT', unset=getwd())
lib <- Sys.getenv(
  'HEALTH_REPORT_R_LIBRARY',
  unset=file.path(project,'.r-library')
)
if(dir.exists(lib)) .libPaths(c(lib,.libPaths()))
rm(project,lib)
