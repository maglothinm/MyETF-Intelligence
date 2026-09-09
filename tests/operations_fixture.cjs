'use strict';
module.exports=function operationsServer(){
  const jobs=Object.fromEntries(['legislative','executive','ai'].map(job=>[job,{job,busy:false,latest_request:null}]));
  const result=(status,value)=>({ok:status<400,status,json:async()=>JSON.parse(JSON.stringify(value))});
  return {jobs,requests:[],failRead:false,failStart:false,beforeStart:null,
    async handle(path,options,session,reviews){
      if(!session.account)return result(401,{code:'SIGN_IN_REQUIRED'});
      if(session.account!=='alice')return result(403,{code:'OPERATOR_REQUIRED'});
      const account_id=reviews.people.get(session.account).id;
      if(options.method!=='POST')return this.failRead?result(503,{code:'RUN_CONTROL_UNAVAILABLE'}):result(200,{account_id,jobs});
      const body=JSON.parse(options.body),job=path.split('/')[1];
      this.requests.push({job,body,options});
      if(this.beforeStart)await this.beforeStart();
      if(this.failStart)throw new Error('Lost network response');
      if(body.expected_account_id!==account_id)return result(409,{code:'ACCOUNT_CHANGED'});
      jobs[job]={job,busy:true,latest_request:{request_id:body.request_id,state:'starting',created_at:Date.now()/1000}};
      return result(202,{account_id,job,latest_request:jobs[job].latest_request});
    }
  };
};
