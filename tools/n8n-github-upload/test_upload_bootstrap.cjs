const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const original=fs.readFileSync(__dirname+'/pilot-bootstrap.cjs','utf8');
assert(original.includes("main().catch("));
const declarationOnly=original.slice(0,original.lastIndexOf("main().catch("));
let lastChildExitCode;
function inspect(env) {
 const timers=[];let exited;
 const context={
  require(name){if(name==='node:events')return {once(){}};return {};},
  process:{env,exit(code){exited=code;throw Error('EXPECTED_EXIT');}},
  Date:class extends Date {static now(){return 1000;}},
  setTimeout(callback,ms){timers.push(ms);return timers.length;},clearTimeout(){},console:{log(){}},
 };
 try {vm.runInNewContext(declarationOnly,context,{timeout:1000});}
 catch(error){if(error.message!=='EXPECTED_EXIT')throw error;}
 lastChildExitCode=context.childExitCode;
 return {timers,exited};
}
assert.deepEqual(inspect({UPLOAD_SERVICE_MODE:'persistent',PILOT_DEADLINE_MS:'0'}),{timers:[],exited:undefined});
assert.deepEqual(inspect({PILOT_DEADLINE_MS:'0'}),{timers:[],exited:0});
assert.deepEqual(inspect({PILOT_DEADLINE_MS:'5000'}),{timers:[4000],exited:undefined});
assert.equal(lastChildExitCode(true,false,0),1);
assert.equal(lastChildExitCode(true,false,null),1);
assert.equal(lastChildExitCode(true,false,137),137);
assert.equal(lastChildExitCode(true,true,0),0);
assert.equal(lastChildExitCode(false,false,0),0);
console.log(JSON.stringify({persistentModeHasNoPilotWatchdog:true,expiredPilotStillStops:true,boundedPilotRetainsExactDeadline:true,unexpectedChildExitTriggersRestart:true,intentionalShutdownPreserved:true}));

