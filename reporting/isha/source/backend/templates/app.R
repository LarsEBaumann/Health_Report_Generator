library(shiny)
source('report_helpers.R')
b <- read_bundle('.')
# Static dashboard visuals and reactive exploration share the same ggplot2 helpers.
# Navigation inside Shiny is handled by tabsetPanel; file downloads use handlers.
findings <- findings_html(b,navigation=FALSE)
findings <- gsub('<a href="methods.html[^"]*">[^<]*</a>','See the Methods & sources tab.',findings)
methods <- methods_html(b,navigation=FALSE,prefix='')
methods <- gsub('<a[^>]*>[^<]*</a>','',methods)
ui <- fluidPage(
  tags$head(tags$style(HTML(paste(readLines('dashboard.css'),collapse='\n')))),
  div(style='max-width:1200px;margin:auto;padding:20px',
    tabsetPanel(
      tabPanel('Findings',HTML(findings)),
      tabPanel('Methods & sources',HTML(methods),
        div(class='trace-controls',h3('Follow a calculation'),
          selectInput('metric','Choose a named metric',setNames(b$metrics$metric_id,paste(b$metrics$subject,b$metrics$metric_type,ifelse(is.na(b$metrics$year),'',b$metrics$year),sep=' · '))),
          tableOutput('metric_value'),tableOutput('lineage'),
          p('For derived inputs, select their metric name to follow the next step.'),
          downloadButton('download_metrics','Download metrics'),downloadButton('download_lineage','Download lineage'))),
      tabPanel('Explore a disease',
        selectInput('topic','Disease',setNames(unique(b$series$topic),b$series$label[match(unique(b$series$topic),b$series$topic)])),
        plotOutput('disease'),p('Source: selected national annual series. Rates are calculated from exported counts and population and may differ slightly from publisher rates based on unrounded counts.'))
    )
  )
)
server <- function(input,output,session) {
  output$disease <- renderPlot({req(input$topic);print(plot_disease(b,input$topic))})
  output$metric_value <- renderTable({req(input$metric);b$metrics[b$metrics$metric_id==input$metric,]})
  output$lineage <- renderTable({req(input$metric);b$lineage[b$lineage$metric_id==input$metric,]})
  output$download_metrics <- downloadHandler(filename=function() 'metrics.csv',content=function(file) file.copy('metrics.csv',file))
  output$download_lineage <- downloadHandler(filename=function() 'lineage.csv',content=function(file) file.copy('lineage.csv',file))
}
shinyApp(ui,server)
