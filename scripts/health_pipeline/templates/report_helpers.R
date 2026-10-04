# Shared presentation only. All metrics and their lineage are calculated in Python.
read_bundle <- function(path = '.') {
  manifest <- jsonlite::fromJSON(file.path(path, 'bundle.json'))
  for(n in names(manifest$files)) {
    if(digest::digest(file=file.path(path,n),algo='sha256') != manifest$files[[n]]) stop(paste('Bundle integrity failed:',n))
  }
  cfg <- jsonlite::fromJSON(file.path(path, 'stakeholder.json'))
  read <- function(n) read.csv(file.path(path, n), stringsAsFactors=FALSE, check.names=FALSE)
  list(cfg=cfg, series=read('series.csv'), metrics=read('metrics.csv'),
       selection=read('selection.csv'), checks=read('checks.csv'), sources=read('sources.csv'),
       lineage=read('lineage.csv'), manifest=jsonlite::fromJSON(file.path(path,'bundle.json')))
}
show_section <- function(b, name) name %in% b$cfg$outputs
headline_table <- function(b) {
  m <- b$metrics
  m[m$metric_type %in% c('period_change','reference_change') & grepl(':main$',m$subject),
    c('metric_id','subject','metric_type','value','unit')]
}
change_table <- function(b) {
  m <- b$metrics
  m[m$metric_type %in% c('period_change','reference_change') & !grepl(':',m$subject),
    c('metric_id','subject','metric_type','value','unit')]
}
plot_groups <- function(b) {
  d <- b$metrics[b$metrics$metric_type=='group_index',]
  subjects <- unique(d$subject)
  yr <- range(d$year); val <- range(c(0,d$value),na.rm=TRUE)
  plot(NA,xlim=yr,ylim=val,xlab='Year',ylab=paste('Index:',b$cfg$index_base_year,'= 100'))
  abline(h=100,col='gray70',lty=3)
  colors <- ifelse(grepl('^viral',subjects),'#b64a23','#00796b')
  for(i in seq_along(subjects)) {
    s <- d[d$subject==subjects[i],]; s <- s[order(s$year),]
    lines(s$year,s$value,type='b',col=colors[i],lwd=2,lty=ifelse(grepl('sensitivity',subjects[i]),2,1))
  }
  legend('topleft',legend=subjects,col=colors,lty=ifelse(grepl('sensitivity',subjects),2,1),cex=.7,bty='n')
}
plot_disease <- function(b,topic,compact=FALSE) {
  s <- b$series[b$series$topic==topic,]; s <- s[order(s$year),]
  plot(s$year,s$incidence,type='b',pch=16,col='#00796b',xlab=if(compact) '' else 'Year',ylab=if(compact) '' else 'Per 100,000',main=s$label[1],xaxt='n')
  axis(1,at=unique(c(min(s$year),b$cfg$years)))
}
plot_small_multiples <- function(b) {
  topics <- unique(b$series$topic)
  old <- par(mfrow=c(ceiling(length(topics)/3),3),mar=c(2.5,3,2.3,1),mgp=c(1.5,.5,0),cex=.8)
  on.exit(par(old))
  for(topic in topics) plot_disease(b,topic,compact=TRUE)
}
