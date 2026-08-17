import{f as a,h as i}from"./index-DDmUh3bQ.js";/**
 * @license lucide-react v0.522.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const c=[["path",{d:"M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2",key:"169zse"}]],g=a("activity",c);/**
 * @license lucide-react v0.522.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const d=[["path",{d:"M8 2v4",key:"1cmpym"}],["path",{d:"M16 2v4",key:"4m81vk"}],["rect",{width:"18",height:"18",x:"3",y:"4",rx:"2",key:"1hopcy"}],["path",{d:"M3 10h18",key:"8toen8"}]],f=a("calendar",d);/**
 * @license lucide-react v0.522.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const u=[["circle",{cx:"12",cy:"12",r:"10",key:"1mglay"}],["rect",{x:"9",y:"9",width:"6",height:"6",rx:"1",key:"1ssd4o"}]],m=a("circle-stop",u);/**
 * @license lucide-react v0.522.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const p=[["polyline",{points:"22 12 16 12 14 15 10 15 8 12 2 12",key:"o97t9d"}],["path",{d:"M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z",key:"oot6mr"}]],v=a("inbox",p);/**
 * @license lucide-react v0.522.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const h=[["path",{d:"M7.9 20A9 9 0 1 0 4 16.1L2 22Z",key:"vv11sd"}]],k=a("message-circle",h);/**
 * @license lucide-react v0.522.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const y=[["path",{d:"M16.247 7.761a6 6 0 0 1 0 8.478",key:"1fwjs5"}],["path",{d:"M19.075 4.933a10 10 0 0 1 0 14.134",key:"ehdyv1"}],["path",{d:"M4.925 19.067a10 10 0 0 1 0-14.134",key:"1q22gi"}],["path",{d:"M7.753 16.239a6 6 0 0 1 0-8.478",key:"r2q7qm"}],["circle",{cx:"12",cy:"12",r:"2",key:"1c9p78"}]],b=a("radio",y);function N(e,t=!1){if(!e)return"";const o=/Z|[+-]\d\d:\d\d$/.test(e)?e:e+"Z",n=new Date(o);if(Number.isNaN(n.getTime()))return"";const r=n.toLocaleTimeString("en-GB",{timeZone:"Asia/Karachi",hour:"2-digit",minute:"2-digit"});if(!t)return r;const s=n.toLocaleDateString("en-GB",{timeZone:"Asia/Karachi",day:"2-digit",month:"short",year:"2-digit"});return`${r}, ${s}`}function _(e){return i("/api/v1/business-profile",e)}function M(e,t){return i("/api/v1/business-profile",e,{method:"POST",body:JSON.stringify(t)})}function O(e,t){return i("/api/v1/business-profile",e,{method:"PUT",body:JSON.stringify(t)})}function S(e){return i("/api/v1/outreach/usage",e)}function $(e){return i("/api/v1/outreach/eligible-leads",e)}function x(e,t){return i("/api/v1/outreach/generate",e,{method:"POST",body:JSON.stringify({lead_ids:t})})}function A(e,t){return i("/api/v1/outreach/regenerate",e,{method:"POST",body:JSON.stringify({lead_id:t})})}function w(e,t){return i("/api/v1/outreach/approve",e,{method:"POST",body:JSON.stringify({items:t})})}function P(e){return i("/api/v1/meetings",e)}function T(e){return i("/api/v1/agent/activity",e)}function L(){return`${"https://crawlioio-production.up.railway.app".replace(/^http/,"ws").replace(/\/$/,"")}/api/v1/agent/ws`}export{g as A,m as C,v as I,k as M,b as R,L as a,_ as b,M as c,f as d,$ as e,S as f,T as g,x as h,w as i,N as k,P as l,A as r,O as u};
