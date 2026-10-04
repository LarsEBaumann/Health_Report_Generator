library(shiny)
source('report_helpers.R')
b <- read_bundle('.')
ui <- fluidPage(
  titlePanel(b$cfg$title),
  p(b$cfg$question),
  p(paste('Geography:',b$cfg$geography,'| Snapshot:',substr(b$manifest$snapshot_id,1,16))),
  p('Uses the same precomputed metrics as the HTML and PDF reports. Filters change the display, not the analysis.'),
  if(show_section(b,'headline')) tableOutput('headlines'),
  if(show_section(b,'group_index')) plotOutput('groups'),
  if(show_section(b,'small_multiples')) tagList(selectInput('topic','Disease',setNames(unique(b$series$topic),b$series$label[match(unique(b$series$topic),b$series$topic)])),plotOutput('disease')),
  if(show_section(b,'group_totals')) tableOutput('totals'),
  if(show_section(b,'change_table')) tableOutput('changes'),
  if(show_section(b,'excluded')) tableOutput('selection'),
  if(show_section(b,'quality')) tableOutput('quality'),
  if(show_section(b,'sources')) tagList(h3('Trace a number'),selectInput('metric','Metric',b$metrics$metric_id),tableOutput('metric_value'),tableOutput('lineage'),p('For derived inputs, select the input metric ID to follow the next step.'),downloadButton('download_metrics','Download metrics'),downloadButton('download_lineage','Download lineage'))
)
server <- function(input,output,session) {
  output$headlines <- renderTable(headline_table(b),digits=2)
  output$groups <- renderPlot(plot_groups(b))
  output$disease <- renderPlot({req(input$topic);plot_disease(b,input$topic)})
  output$totals <- renderTable(b$metrics[b$metrics$metric_type=='group_total',c('metric_id','subject','year','value')])
  output$changes <- renderTable(change_table(b),digits=2)
  output$selection <- renderTable(b$selection[,c('topic','status','reason','group_eligible')])
  output$quality <- renderTable(as.data.frame(table(b$checks$status)))
  output$metric_value <- renderTable({req(input$metric);b$metrics[b$metrics$metric_id==input$metric,]})
  output$lineage <- renderTable({req(input$metric);b$lineage[b$lineage$metric_id==input$metric,]})
  output$download_metrics <- downloadHandler(filename=function() 'metrics.csv',content=function(file) file.copy('metrics.csv',file))
  output$download_lineage <- downloadHandler(filename=function() 'lineage.csv',content=function(file) file.copy('lineage.csv',file))
}
shinyApp(ui,server)
