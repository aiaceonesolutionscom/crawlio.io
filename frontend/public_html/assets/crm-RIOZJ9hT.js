import{f as r,h as i}from"./index-DDmUh3bQ.js";/**
 * @license lucide-react v0.522.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const t=[["circle",{cx:"12",cy:"12",r:"10",key:"1mglay"}],["path",{d:"M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20",key:"13o1zl"}],["path",{d:"M2 12h20",key:"9i4pu4"}]],s=r("globe",t);function c(e){return i("/api/v1/leads/ai-filter",e)}function o(e,a){return i("/api/v1/leads/ai-filter/enrich",e,{method:"POST",body:JSON.stringify({lead_ids:a})})}function d(e,a){return i("/api/v1/crm/entries",e,{method:"POST",body:JSON.stringify({lead_ids:a})})}function l(e){return i("/api/v1/crm/entries",e)}export{s as G,c as a,o as b,d as c,l};
