# pppoe-dashboard
First off I am not a programmer, I work on network gear all day long and recently the company I work for changed the backend billing system which came with it's own RADIUS but with no API access. I wanted to have a view of all the current connected subscribers ( L2TP, PPPoE and PPPoE over LT2P ) 
This is currently working pulling data from 2x Cisco ASR1001x's with around 5k subscribers and it completes a run in under 30s.
I thought there may be a use for this for other people in a similar situation, so here it is.
The plan is to extend this to support other BNG's probably Mikrotik since I see that is used by smaller ISP's.
