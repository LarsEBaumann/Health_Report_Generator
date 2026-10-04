# Run explicitly after reviewing a dependency upgrade, never on ordinary builds.
roots <- c('shiny','knitr','rmarkdown','jsonlite','digest','ggplot2')
installed <- installed.packages()
deps <- tools::package_dependencies(roots,db=installed,which=c('Depends','Imports','LinkingTo'),recursive=TRUE)
names_all <- sort(unique(c(roots,unlist(deps))))
names_all <- names_all[names_all %in% rownames(installed)]
names_all <- names_all[is.na(installed[names_all,'Priority']) | installed[names_all,'Priority']=='']
# Preserve the literal DESCRIPTION version: packageVersion() normalizes hyphens
# to dots, which breaks repository downloads (e.g. RColorBrewer 1.1-3).
records <- setNames(lapply(names_all,function(p) {
  req <- tools::package_dependencies(p,db=installed,which=c('Depends','Imports','LinkingTo'))[[p]]
  list(Package=p,Version=unname(installed[p,'Version']),Source='Repository',Repository='CRAN',Requirements=I(sort(intersect(req,names_all))))
}),names_all)
lock <- list(R=list(Version=as.character(getRversion()),Repositories=list(list(Name='CRAN',URL='https://cloud.r-project.org'))),Packages=records)
jsonlite::write_json(lock,'renv.lock',pretty=TRUE,auto_unbox=TRUE)
