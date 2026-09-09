'use strict';
// In-memory HTTP fixture for UI behavior. Database and auth guarantees are
// separately exercised by test_personal_reviews.py, including PostgreSQL CI.
module.exports = function reviewServer() {
  const people = new Map(['alice','bob'].map((name,i)=>[name,{id:`00000000-0000-4000-8000-${String(i+1).padStart(12,'0')}`,username:name,revision:0,rows:new Map()}]));
  const result = (status,value)=>({ok:status<400,status,json:async()=>JSON.parse(JSON.stringify(value))});
  const state = person=>({authenticated:true,version:1,account:{id:person.id,username:person.username},revision:person.revision,
    acknowledged:[...person.rows.values()].filter(Boolean)});
  const server={people,requests:[],failRead:false,failSave:false,beforeSave:null,state:name=>state(people.get(name)),
    async handle(route,options,session,model) {
      const body=options.body?JSON.parse(options.body):null;
      this.requests.push({route,body});
      if(route==='login'||route==='activate'){session.account=route==='activate'?'alice':body.username;return result(200,state(people.get(session.account)));}
      if(route==='logout'){session.account=null;return result(200,{authenticated:false});}
      if(this.failRead&&route==='session')return result(503,{code:'REVIEWS_UNAVAILABLE'});
      if(!session.account)return route==='session'?result(200,{authenticated:false}):result(401,{code:'SIGN_IN_REQUIRED',message:'Sign in to load your saved reviews.'});
      const person=people.get(session.account);
      if(route==='session'||route==='state')return result(200,state(person));
      if(body.expected_account_id!==person.id)return result(409,{code:'ACCOUNT_CHANGED',message:'The signed-in account changed. Refresh before saving a review.'});
      if(route==='acknowledgements'){
        if(this.beforeSave)await this.beforeSave();
        if(this.failSave)return result(503,{code:'REVIEWS_UNAVAILABLE',message:'SQL details must not reach the UI'});
        if(body.expected_revision!==person.revision)return result(409,{code:'REVIEW_CHANGED',message:'Your saved reviews changed in another session. Refresh and try again.'});
        if(model.reviews.manual_exception_identities?.[body.review_id]!==body.logical_review_id)return result(409,{code:'REVIEW_CHANGED',message:'The retained review changed.'});
        person.rows.set(body.logical_review_id,body.acknowledged?{id:body.review_id,logical_review_id:body.logical_review_id,acknowledged_at_utc:'2026-08-30T12:00:00Z'}:null);
        person.revision++;return result(200,state(person));
      }
      if(route==='import'){
        let imported=0;
        for(const row of body.acknowledged){const identity=model.reviews.manual_exception_identities?.[row.id];if(identity&&!person.rows.has(identity)){person.rows.set(identity,{...row,logical_review_id:identity});person.revision++;imported++;}}
        return result(200,{...state(person),imported,unmatched:0});
      }
      return result(404,{code:'NOT_FOUND'});
    }};
  return server;
};
