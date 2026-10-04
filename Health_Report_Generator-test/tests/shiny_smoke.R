args <- commandArgs(trailingOnly=TRUE)
setwd(args[1])
env <- new.env()
sys.source('app.R',env)
shiny::testServer(env$server, {
  session$setInputs(topic='influenza',metric='influenza:2025:count')
  stopifnot(nchar(output$headlines)>0,nchar(output$metric_value)>0,nchar(output$lineage)>0)
})
cat('Shiny server outputs passed\n')
