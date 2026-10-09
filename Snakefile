# Preserve the original report while the request interface is introduced.
configfile: 'workflow/config.yaml'
if config.get('request_file'):
    include: 'workflow/request.smk'
else:
    include: 'workflow/legacy.smk'

# Includes restore the caller's default target; declare it explicitly here.
rule entrypoint:
    default_target: True
    input: rules.all.input
