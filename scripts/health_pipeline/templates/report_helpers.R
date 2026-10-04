# Shared presentation only. All metrics and their lineage are calculated in Python.
read_bundle <- function(path = '.') {
  manifest <- jsonlite::fromJSON(file.path(path, 'bundle.json'))
  for(n in names(manifest$files)) {
    if(digest::digest(file=file.path(path,n),algo='sha256') != manifest$files[[n]]) stop(paste('Bundle integrity failed:',n))
  }
  cfg <- jsonlite::fromJSON(file.path(path, 'stakeholder.json'))
  read <- function(n) read.csv(file.path(path, n), stringsAsFactors=FALSE, check.names=FALSE)
  list(cfg=cfg, classes=read('pathogen_class.csv'), series=read('series.csv'), metrics=read('metrics.csv'),
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

esc <- function(x) as.character(htmltools::htmlEscape(as.character(x)))
metric_value <- function(b,id) { x<-b$metrics$value[match(id,b$metrics$metric_id)]; if(length(x)) x else NA_real_ }
format_pct <- function(x,digits=0) ifelse(is.na(x),'Not available',sprintf(paste0('%+.',digits,'f%%'),x))
label_topic <- function(b,x) {
  labels<-setNames(b$classes$label,b$classes$topic)
  ifelse(x %in% names(labels),labels[x],gsub('_',' ',x,fixed=TRUE))
}
report_year <- function(b) b$cfg$years[2]
sensitivity_label <- function(b) paste(label_topic(b,b$cfg$sensitivity_exclude),collapse=', ')
group_topics <- function(b) unique(b$selection$topic[b$selection$status=='included' & tolower(as.character(b$selection$group_eligible))=='true'])
report_theme <- function() ggplot2::theme_minimal(base_size=13,base_family='sans') +
  ggplot2::theme(panel.grid.minor=ggplot2::element_blank(),panel.grid.major.x=ggplot2::element_blank(),
  panel.grid.major.y=ggplot2::element_line(colour='#dfe6e5',linewidth=.3),
  plot.background=ggplot2::element_rect(fill='white',colour=NA),panel.background=ggplot2::element_rect(fill='white',colour=NA),
  text=ggplot2::element_text(colour='#18343c'),axis.text=ggplot2::element_text(colour='#52656b',size=12),
  axis.title=ggplot2::element_text(size=11),legend.position='top',legend.title=ggplot2::element_blank(),legend.text=ggplot2::element_text(size=11),plot.margin=ggplot2::margin(12,15,5,5))
plot_group_totals <- function(b) {
  d<-b$metrics[b$metrics$metric_type=='group_total' & b$metrics$subject %in% c('viral:main','bacterial:main'),]
  d$group<-factor(d$subject,levels=c('viral:main','bacterial:main'),labels=c('Viral','Bacterial'))
  ggplot2::ggplot(d,ggplot2::aes(factor(year),value,fill=group))+
    ggplot2::geom_col(position=ggplot2::position_dodge(width=.74),width=.64)+
    ggplot2::scale_fill_manual(values=c('Viral'='#b95d35','Bacterial'='#247c85'))+
    ggplot2::scale_y_continuous(labels=function(x)paste0(x/1000,'k'),expand=ggplot2::expansion(mult=c(0,.08)))+
    ggplot2::labs(x=NULL,y='Reported cases')+report_theme()
}
plot_groups <- function(b) {
  subjects<-c('viral:main','bacterial:main');labels<-c('Viral','Bacterial')
  if(length(b$cfg$sensitivity_exclude)){subjects<-c(subjects,'viral:sensitivity');labels<-c(labels,paste('Viral without',sensitivity_label(b)))}
  d<-b$metrics[b$metrics$metric_type=='group_index' & b$metrics$subject %in% subjects,]
  d$group<-factor(d$subject,levels=subjects,labels=labels)
  # Display the existing index in percentage-change units; no series is reselected.
  d$change<-d$value-100
  ggplot2::ggplot(d,ggplot2::aes(year,change,colour=group,linetype=group))+
    ggplot2::geom_hline(yintercept=0,colour='#9fb0b2',linewidth=.4)+ggplot2::geom_line(linewidth=1)+ggplot2::geom_point(size=2)+
    ggplot2::scale_colour_manual(values=setNames(c('#b95d35','#247c85','#7e728e')[seq_along(subjects)],labels))+
    ggplot2::scale_linetype_manual(values=setNames(c('solid','solid','dashed')[seq_along(subjects)],labels))+
    ggplot2::scale_x_continuous(breaks=sort(unique(c(b$cfg$index_base_year,b$cfg$years[1],b$cfg$years[2]-2,b$cfg$years[2]))))+
    ggplot2::scale_y_continuous(labels=function(x)paste0(ifelse(x>0,'+',''),x,'%'))+
    ggplot2::labs(x=NULL,y=paste('Change from',b$cfg$index_base_year))+report_theme()+
    ggplot2::guides(colour=ggplot2::guide_legend(nrow=2),linetype=ggplot2::guide_legend(nrow=2))
}
friendly_changes <- function(b) {
  d<-b$metrics[b$metrics$metric_type=='reference_change' & b$metrics$subject %in% group_topics(b),]
  d<-d[order(d$value,decreasing=TRUE),];topics<-d$subject
  count_at<-function(y) b$series$value[match(paste(topics,y),paste(b$series$topic,b$series$year))]
  data.frame(Disease=label_topic(b,topics),Baseline=count_at(b$cfg$reference_year),Latest=count_at(report_year(b)),Change=d$value,check.names=FALSE)
}
plot_changes <- function(b) {
  d<-friendly_changes(b);d$Disease<-factor(d$Disease,levels=rev(d$Disease))
  ggplot2::ggplot(d,ggplot2::aes(Change,Disease))+
    ggplot2::geom_vline(xintercept=0,colour='#9fb0b2',linewidth=.4)+
    ggplot2::geom_segment(ggplot2::aes(x=0,xend=Change,yend=Disease),colour='#c0d0d1',linewidth=2)+ggplot2::geom_point(colour='#247c85',size=3)+
    ggplot2::scale_x_continuous(labels=function(x)paste0(ifelse(x>0,'+',''),x,'%'))+
    ggplot2::labs(x=paste('Change in reported cases,',report_year(b),'versus',b$cfg$reference_year),y=NULL)+
    report_theme()+ggplot2::theme(panel.grid.major.y=ggplot2::element_blank(),panel.grid.major.x=ggplot2::element_line(colour='#dfe6e5',linewidth=.3))
}
plot_disease <- function(b,topic,compact=FALSE) {
  s<-b$series[b$series$topic==topic,]
  ggplot2::ggplot(s,ggplot2::aes(year,incidence)) + ggplot2::geom_line(colour='#247c85',linewidth=1)+ggplot2::geom_point(colour='#247c85',size=2)+
    ggplot2::labs(title=s$label[1],x='Year',y='Per 100,000 people')+report_theme()
}
plot_small_multiples <- function(b) {
  ggplot2::ggplot(b$series,ggplot2::aes(year,incidence))+ggplot2::geom_line(colour='#247c85')+
    ggplot2::geom_point(colour='#247c85',size=1)+ggplot2::facet_wrap(~label,scales='free_y',ncol=3)+
    ggplot2::labs(x='Year',y='Per 100,000 people')+report_theme()
}
chart_image <- function(plot,alt,width=6,height=3.8) {
  p<-tempfile(fileext='.png');on.exit(unlink(p));ggplot2::ggsave(p,plot,width=width,height=height,dpi=180,bg='white')
  paste0('<img alt="',esc(alt),'" src="',knitr::image_uri(p),'">')
}
report_navigation <- function(b,methods=FALSE,format='html') {
  paste0('<header class="dash-nav"><span class="dash-brand">SURVEILLANCE / ',if(b$cfg$geography=='CHFL')'SWITZERLAND + LIECHTENSTEIN' else 'SWITZERLAND','</span><nav aria-label="Reports">',
         if(!methods)'<span class="nav-active">Findings</span>' else '<a href="report.html">Findings</a>',
         if(methods)'<span class="nav-active">Methods &amp; sources</span>' else '<a href="methods.html">Methods &amp; sources</a>',
         '<a href="',if(methods)'methods.pdf' else 'report.pdf','">PDF version</a></nav></header>')
}
report_metadata <- function(b) paste0('<div class="report-meta"><span>',length(group_topics(b)),' diseases in the group comparison</span><span>National case notifications</span><span class="snapshot">Snapshot ',substr(b$manifest$snapshot_id,1,16),'</span></div>')
summary_cards <- function(b) {
  ids<-c('viral:main:reference_change','bacterial:main:reference_change');labels<-c('Viral notifications','Bacterial notifications')
  if(length(b$cfg$sensitivity_exclude)){ids<-c(ids,'viral:sensitivity:reference_change');labels<-c(labels,paste('Viral, without',sensitivity_label(b)))}
  paste0('<div class="metric-grid">',paste(vapply(seq_along(ids),function(i)paste0('<article class="metric-card"><div class="metric-label">',esc(labels[i]),'</div><div class="metric-value">',format_pct(metric_value(b,ids[i])),'</div><p>',report_year(b),' compared with ',b$cfg$reference_year,'</p></article>'),character(1)),collapse=''),'</div>')
}
friendly_table <- function(b) {
  d<-friendly_changes(b);d$Baseline<-format(d$Baseline,big.mark=',',scientific=FALSE,trim=TRUE);d$Latest<-format(d$Latest,big.mark=',',scientific=FALSE,trim=TRUE);d$Change<-format_pct(d$Change,1)
  names(d)<-c('Disease',paste('Cases in',b$cfg$reference_year),paste('Cases in',report_year(b)),'Change')
  d
}
html_table <- function(d) paste0('<div class="table-scroll">',as.character(knitr::kable(d,format='html',escape=TRUE,row.names=FALSE,table.attr='class="report-table"')),'</div>')
findings_html <- function(b,navigation=TRUE) {
  panel<-function(title,caption,plot,note,width=6,height=3.8) paste0('<section class="chart-panel"><h2>',esc(title),'</h2><p class="caption">',esc(caption),'</p>',chart_image(plot,title,width,height),'<div class="chart-note">',note,'</div></section>')
  year<-report_year(b);ref<-b$cfg$reference_year
  excluded<-paste(label_topic(b,b$cfg$exclude_from_group_totals),collapse=', ')
  rising <- all(c(metric_value(b,'viral:main:reference_change'),metric_value(b,'bacterial:main:reference_change'))>0,na.rm=FALSE)
  title <- if(isTRUE(rising)) paste0('More notifications in ',year,'.<br>Different patterns behind the rise.') else paste0('Disease notifications:<br>the ',year,' picture.')
  concentrated <- length(b$cfg$sensitivity_exclude)>0 && isTRUE(metric_value(b,'viral:main:reference_change')>0 && metric_value(b,'viral:sensitivity:reference_change')<=0)
  change_title <- if(concentrated) paste('The viral rise is concentrated in',sensitivity_label(b)) else if(length(b$cfg$sensitivity_exclude)) paste('How does excluding',sensitivity_label(b),'change the picture?') else 'How have the groups changed?'
  parts<-c('<div class="dashboard">',if(navigation)report_navigation(b),paste0('<div class="eyebrow">Annual disease briefing · ',paste(b$cfg$years,collapse='–'),' · comparison with ',ref,'</div><h1>',title,'</h1>'),report_metadata(b))
  if(show_section(b,'headline'))parts<-c(parts,summary_cards(b))
  parts<-c(parts,'<div class="chart-grid">')
  if(show_section(b,'group_totals'))parts<-c(parts,panel('How many cases were reported?','Annual totals for the selected diseases',plot_group_totals(b),paste0('Source: FOPH dashboard exports · sum of selected national case notifications. ',esc(excluded),' excluded. Only the reference and configured reporting years are shown. <a href="methods.html#selection">How calculated</a>')))
  if(show_section(b,'group_index'))parts<-c(parts,panel(change_title,paste0('Change from ',b$cfg$index_base_year,'; 0% means the same number of cases'),plot_groups(b),'Source: the same selected case series · percentage change from each group’s baseline total. This compares trends, not absolute disease burden. <a href="methods.html#calculations">How calculated</a>'))
  parts<-c(parts,'</div>')
  if(show_section(b,'small_multiples'))parts<-c(parts,paste0('<section class="chart-panel full"><h2>Which diseases changed most?</h2><p class="caption">Reported cases in ',year,' compared with ',ref,'</p>',chart_image(plot_changes(b),'Disease-specific changes in reported cases',9,4.7),'<div class="chart-note">Source: selected national FOPH case series. Right of zero = more notifications; left = fewer. Percentage changes do not measure disease severity or statistical significance.</div>'))
  if(show_section(b,'change_table'))parts<-c(parts,paste0('<details><summary>View the figures behind the comparison</summary>',html_table(friendly_table(b)),'<div class="table-note">Source: selected FOPH annual national case counts. Change = (latest count − baseline count) ÷ baseline count × 100. Values are rounded for display. <a href="methods.html#calculations">View calculation details</a></div></details>'))
  if(show_section(b,'small_multiples'))parts<-c(parts,'</section>')
  parts<-c(parts,'<footer class="dash-footer"><span>Notifications reflect surveillance and testing as well as disease occurrence.</span><a href="methods.html">Read the methods &amp; source report →</a></footer></div>')
  paste(parts,collapse='\n')
}
methods_html <- function(b,navigation=TRUE,prefix='data/') {
  y<-report_year(b);ref<-b$cfg$reference_year;a<-metric_value(b,paste0('viral:main:',ref,':total'));z<-metric_value(b,paste0('viral:main:',y,':total'))
  fmt<-function(x)format(x,big.mark=',',scientific=FALSE,trim=TRUE)
  row<-function(k,v)paste0('<div class="audit-row"><span>',esc(k),'</span><strong>',esc(v),'</strong></div>')
  selected<-b$selection[,c('topic','status','reason','group_eligible')];selected$topic<-label_topic(b,selected$topic);selected$group_eligible<-ifelse(tolower(as.character(selected$group_eligible))=='true','Yes','No');names(selected)<-c('Disease or signal','Selection','Reason','In main group')
  sources<-b$sources[b$sources$status=='ok',c('topic','publishing_date','used')];sources$topic<-label_topic(b,sources$topic);sources$used<-ifelse(tolower(as.character(sources$used))=='true','Yes','No');names(sources)<-c('Disease or signal','Published','Used in analysis')
  quality<-as.data.frame(table(b$checks$status));names(quality)<-c('Check result','Number of checks')
  parts<-c('<div class="dashboard">',if(navigation)report_navigation(b,TRUE),'<div class="eyebrow">Companion report / Methods &amp; sources</div><h1>Where the findings come from.</h1>',report_metadata(b),'<div class="audit-grid"><section class="audit-panel" id="selection"><h2>What is included?</h2>',row('Geography',if(b$cfg$geography=='CHFL')'Switzerland + Liechtenstein' else 'Switzerland'),row('Reporting years',paste(b$cfg$years,collapse='–')),row('Reference year',ref))
  for(cls in c('viral','bacterial')) { topics<-unique(b$series$topic[b$series$pathogen_class==cls & b$series$topic %in% group_topics(b)]);parts<-c(parts,row(paste(tools::toTitleCase(cls),'group'),paste(length(topics),'diseases')),paste0('<p class="caption">',esc(paste(label_topic(b,topics),collapse=', ')),'.</p>')) }
  parts<-c(parts,paste0('<div class="chart-note">Excluded from group sums: ',esc(paste(label_topic(b,b$cfg$exclude_from_group_totals),collapse=', ')),'. Sentinel estimates are not pooled with mandatory case notifications.</div></section><section class="audit-panel" id="calculations"><h2>Trace a finding, not a code</h2><h3>Viral notifications: ',format_pct(metric_value(b,'viral:main:reference_change'),1),' versus ',ref,'</h3>'),row(paste('Selected cases in',y),fmt(z)),row(paste('Selected cases in',ref),fmt(a)),row('Calculation',paste0('(',fmt(z),' − ',fmt(a),') ÷ ',fmt(a),' × 100')),'<p class="caption">The lineage export links these totals to each disease, then to its original source records. It includes the population denominator for calculated rates.</p></section></div>')
  if(show_section(b,'excluded'))parts<-c(parts,paste0('<section class="audit-panel full"><h2>Dataset selection</h2>',html_table(selected),'<div class="table-note">Source: the saved selection table. “Included” means eligible for disease-level analysis; “In main group” additionally applies the configured source and disease exclusions.</div></section>'))
  if(show_section(b,'quality'))parts<-c(parts,paste0('<section class="audit-panel full"><h2>Data quality</h2>',html_table(quality),'<div class="table-note">Source: automated checks on the full harmonised snapshot. PASS meets the rule; WARN needs interpretation; SKIP means no compatible data for that check. A critical FAIL blocks publication.</div></section>'))
  if(show_section(b,'sources'))parts<-c(parts,paste0('<section class="audit-panel full"><h2>Sources and audit files</h2>',html_table(sources),'<div class="table-note">Source: the dataset registry and original export descriptions. Dates are publisher release dates. Full paths, data and metadata fingerprints are retained in the downloadable source registry.</div><div class="download-links">',paste(vapply(c('sources.csv','selection.csv','lineage.csv','metrics.csv','checks.csv','snapshot.json'),function(n)paste0('<a download href="',prefix,n,'">',esc(n),'</a>'),character(1)),collapse=''),'</div><details><summary>Technical identifiers and exact snapshot</summary><p class="snapshot">',esc(b$manifest$snapshot_id),'</p><p>Full metric identifiers are in metrics.csv. The findings report uses human-readable names instead of printed M-codes. CSV record numbers count the header as record 1; multiline CSV fields may span several text lines.</p></details></section>'))
  parts<-c(parts,'<footer class="dash-footer"><span>Descriptive comparisons do not establish causes, severity or statistical significance.</span><a href="report.html">← Back to findings</a></footer></div>');paste(parts,collapse='\n')
}
