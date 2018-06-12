'''
AuTest-based testing for the Superior Cache ANalyzer
'''

import os
import sys
Test.Summary = 'Test The Superior Cache ANalyzer'


# Needs Curl
Test.SkipUnless(
    Condition.HasProgram("curl", "curl needs to be installed on system for this test to work")
)
Test.ContinueOnFail = False

# Define default ATS
ts = Test.MakeATSProcess("ts")
server = Test.MakeOriginServer("server")

#**testname is required**
testName = ""
request_header = {"headers": "GET / HTTP/1.1\r\nHost: www.example.com\r\n\r\n", "timestamp": "1469733493.993", "body": ""}
response_header = {"headers": "HTTP/1.1 200 OK\r\nConnection: close\r\nCache-Control: max-age=999999,public\r\n\r\n", "timestamp": "1469733493.993", "body": "yabadabadoo"}
server.addResponse("sessionlog.json", request_header, response_header)

# ATS Configuration
ts.Disk.plugin_config.AddLine('xdebug.so')
ts.Disk.records_config.update({
    'proxy.config.diags.debug.enabled': 1,
    'proxy.config.diags.debug.tags': 'http|cache',
    'proxy.config.http.response_via_str': 3,
    'proxy.config.http.cache.http': 1,
    'proxy.config.http.wait_for_cache': 1,
	'proxy.config.cache.ram_cache.size': 0,
    'proxy.config.config_update_interval_ms': 1,
    'proxy.config.http.cache.required_headers': 0,
    'proxy.config.cache.dir.sync_frequency': 1
})

ts.Disk.remap_config.AddLine(
    'map / http://127.0.0.1:{0}'.format(server.Variables.Port)
)

ts.Disk.volume_config.AddLine('volume=1 scheme=http size=100%')

request = 'curl -s -D - -v --ipv4 --http1.1 -H "x-debug: x-cache,via" -H "Host: www.example.com" http://localhost:{port}/'.format(port=ts.Variables.port)

# Test 1 - 200 response and cache fill
tr = Test.AddTestRun()
tr.Processes.Default.StartBefore(server)
tr.Processes.Default.StartBefore(Test.Processes.ts, ready=1)
tr.Processes.Default.Command = request
tr.Processes.Default.ReturnCode = 0
tr.Processes.Default.Streams.stdout = "gold/cache_populated.gold"
tr.StillRunningAfter = ts

# At this point, there should be something(TM) in the cache...
# ... although at the time of this writing, there is not.
tr = Test.AddTestRun()
tr.Setup.Copy('test.py')
tr.Processes.Default.Command = 'sleep 2 && ls -R etc && {0} ./test.py --ats_root ts --ats_configs etc'.format(sys.executable if sys.executable else 'python3')
tr.Processes.Default.ReturnCode = 0
