var Ut=Object.defineProperty;var Mt=(o,t,e)=>t in o?Ut(o,t,{enumerable:!0,configurable:!0,writable:!0,value:e}):o[t]=e;var D=(o,t,e)=>Mt(o,typeof t!="symbol"?t+"":t,e);var H=globalThis,T=H.ShadowRoot&&(H.ShadyCSS===void 0||H.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,I=Symbol(),it=new WeakMap,E=class{constructor(t,e,s){if(this._$cssResult$=!0,s!==I)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o,e=this.t;if(T&&t===void 0){let s=e!==void 0&&e.length===1;s&&(t=it.get(e)),t===void 0&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),s&&it.set(e,t))}return t}toString(){return this.cssText}},ot=o=>new E(typeof o=="string"?o:o+"",void 0,I),j=(o,...t)=>{let e=o.length===1?o[0]:t.reduce((s,i,n)=>s+(r=>{if(r._$cssResult$===!0)return r.cssText;if(typeof r=="number")return r;throw Error("Value passed to 'css' function must be a 'css' function result: "+r+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+o[n+1],o[0]);return new E(e,o,I)},nt=(o,t)=>{if(T)o.adoptedStyleSheets=t.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let e of t){let s=document.createElement("style"),i=H.litNonce;i!==void 0&&s.setAttribute("nonce",i),s.textContent=e.cssText,o.appendChild(s)}},V=T?o=>o:o=>o instanceof CSSStyleSheet?(t=>{let e="";for(let s of t.cssRules)e+=s.cssText;return ot(e)})(o):o;var{is:Nt,defineProperty:Rt,getOwnPropertyDescriptor:Ht,getOwnPropertyNames:Tt,getOwnPropertySymbols:Lt,getPrototypeOf:zt}=Object,L=globalThis,rt=L.trustedTypes,Bt=rt?rt.emptyScript:"",Dt=L.reactiveElementPolyfillSupport,C=(o,t)=>o,W={toAttribute(o,t){switch(t){case Boolean:o=o?Bt:null;break;case Object:case Array:o=o==null?o:JSON.stringify(o)}return o},fromAttribute(o,t){let e=o;switch(t){case Boolean:e=o!==null;break;case Number:e=o===null?null:Number(o);break;case Object:case Array:try{e=JSON.parse(o)}catch{e=null}}return e}},lt=(o,t)=>!Nt(o,t),at={attribute:!0,type:String,converter:W,reflect:!1,useDefault:!1,hasChanged:lt};Symbol.metadata??=Symbol("metadata"),L.litPropertyMetadata??=new WeakMap;var f=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=at){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){let s=Symbol(),i=this.getPropertyDescriptor(t,s,e);i!==void 0&&Rt(this.prototype,t,i)}}static getPropertyDescriptor(t,e,s){let{get:i,set:n}=Ht(this.prototype,t)??{get(){return this[e]},set(r){this[e]=r}};return{get:i,set(r){let p=i?.call(this);n?.call(this,r),this.requestUpdate(t,p,s)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??at}static _$Ei(){if(this.hasOwnProperty(C("elementProperties")))return;let t=zt(this);t.finalize(),t.l!==void 0&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(C("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(C("properties"))){let e=this.properties,s=[...Tt(e),...Lt(e)];for(let i of s)this.createProperty(i,e[i])}let t=this[Symbol.metadata];if(t!==null){let e=litPropertyMetadata.get(t);if(e!==void 0)for(let[s,i]of e)this.elementProperties.set(s,i)}this._$Eh=new Map;for(let[e,s]of this.elementProperties){let i=this._$Eu(e,s);i!==void 0&&this._$Eh.set(i,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){let e=[];if(Array.isArray(t)){let s=new Set(t.flat(1/0).reverse());for(let i of s)e.unshift(V(i))}else t!==void 0&&e.push(V(t));return e}static _$Eu(t,e){let s=e.attribute;return s===!1?void 0:typeof s=="string"?s:typeof t=="string"?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),this.renderRoot!==void 0&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){let t=new Map,e=this.constructor.elementProperties;for(let s of e.keys())this.hasOwnProperty(s)&&(t.set(s,this[s]),delete this[s]);t.size>0&&(this._$Ep=t)}createRenderRoot(){let t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return nt(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,s){this._$AK(t,s)}_$ET(t,e){let s=this.constructor.elementProperties.get(t),i=this.constructor._$Eu(t,s);if(i!==void 0&&s.reflect===!0){let n=(s.converter?.toAttribute!==void 0?s.converter:W).toAttribute(e,s.type);this._$Em=t,n==null?this.removeAttribute(i):this.setAttribute(i,n),this._$Em=null}}_$AK(t,e){let s=this.constructor,i=s._$Eh.get(t);if(i!==void 0&&this._$Em!==i){let n=s.getPropertyOptions(i),r=typeof n.converter=="function"?{fromAttribute:n.converter}:n.converter?.fromAttribute!==void 0?n.converter:W;this._$Em=i;let p=r.fromAttribute(e,n.type);this[i]=p??this._$Ej?.get(i)??p,this._$Em=null}}requestUpdate(t,e,s,i=!1,n){if(t!==void 0){let r=this.constructor;if(i===!1&&(n=this[t]),s??=r.getPropertyOptions(t),!((s.hasChanged??lt)(n,e)||s.useDefault&&s.reflect&&n===this._$Ej?.get(t)&&!this.hasAttribute(r._$Eu(t,s))))return;this.C(t,e,s)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(t,e,{useDefault:s,reflect:i,wrapped:n},r){s&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,r??e??this[t]),n!==!0||r!==void 0)||(this._$AL.has(t)||(this.hasUpdated||s||(e=void 0),this._$AL.set(t,e)),i===!0&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let t=this.scheduleUpdate();return t!=null&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[i,n]of this._$Ep)this[i]=n;this._$Ep=void 0}let s=this.constructor.elementProperties;if(s.size>0)for(let[i,n]of s){let{wrapped:r}=n,p=this[i];r!==!0||this._$AL.has(i)||p===void 0||this.C(i,void 0,n,p)}}let t=!1,e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(s=>s.hostUpdate?.()),this.update(e)):this._$EM()}catch(s){throw t=!1,this._$EM(),s}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(t){}firstUpdated(t){}};f.elementStyles=[],f.shadowRootOptions={mode:"open"},f[C("elementProperties")]=new Map,f[C("finalized")]=new Map,Dt?.({ReactiveElement:f}),(L.reactiveElementVersions??=[]).push("2.1.2");var X=globalThis,ct=o=>o,z=X.trustedTypes,ht=z?z.createPolicy("lit-html",{createHTML:o=>o}):void 0,ft="$lit$",g=`lit$${Math.random().toFixed(9).slice(2)}$`,gt="?"+g,It=`<${gt}>`,b=document,k=()=>b.createComment(""),O=o=>o===null||typeof o!="object"&&typeof o!="function",Z=Array.isArray,jt=o=>Z(o)||typeof o?.[Symbol.iterator]=="function",F=`[ 	
\f\r]`,P=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,pt=/-->/g,dt=/>/g,y=RegExp(`>|${F}(?:([^\\s"'>=/]+)(${F}*=${F}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),ut=/'/g,mt=/"/g,$t=/^(?:script|style|textarea|title)$/i,Q=o=>(t,...e)=>({_$litType$:o,strings:t,values:e}),u=Q(1),ee=Q(2),se=Q(3),x=Symbol.for("lit-noChange"),l=Symbol.for("lit-nothing"),_t=new WeakMap,v=b.createTreeWalker(b,129);function yt(o,t){if(!Z(o)||!o.hasOwnProperty("raw"))throw Error("invalid template strings array");return ht!==void 0?ht.createHTML(t):t}var Vt=(o,t)=>{let e=o.length-1,s=[],i,n=t===2?"<svg>":t===3?"<math>":"",r=P;for(let p=0;p<e;p++){let a=o[p],c,d,h=-1,m=0;for(;m<a.length&&(r.lastIndex=m,d=r.exec(a),d!==null);)m=r.lastIndex,r===P?d[1]==="!--"?r=pt:d[1]!==void 0?r=dt:d[2]!==void 0?($t.test(d[2])&&(i=RegExp("</"+d[2],"g")),r=y):d[3]!==void 0&&(r=y):r===y?d[0]===">"?(r=i??P,h=-1):d[1]===void 0?h=-2:(h=r.lastIndex-d[2].length,c=d[1],r=d[3]===void 0?y:d[3]==='"'?mt:ut):r===mt||r===ut?r=y:r===pt||r===dt?r=P:(r=y,i=void 0);let _=r===y&&o[p+1].startsWith("/>")?" ":"";n+=r===P?a+It:h>=0?(s.push(c),a.slice(0,h)+ft+a.slice(h)+g+_):a+g+(h===-2?p:_)}return[yt(o,n+(o[e]||"<?>")+(t===2?"</svg>":t===3?"</math>":"")),s]},U=class o{constructor({strings:t,_$litType$:e},s){let i;this.parts=[];let n=0,r=0,p=t.length-1,a=this.parts,[c,d]=Vt(t,e);if(this.el=o.createElement(c,s),v.currentNode=this.el.content,e===2||e===3){let h=this.el.content.firstChild;h.replaceWith(...h.childNodes)}for(;(i=v.nextNode())!==null&&a.length<p;){if(i.nodeType===1){if(i.hasAttributes())for(let h of i.getAttributeNames())if(h.endsWith(ft)){let m=d[r++],_=i.getAttribute(h).split(g),A=/([.?@])?(.*)/.exec(m);a.push({type:1,index:n,name:A[2],strings:_,ctor:A[1]==="."?K:A[1]==="?"?J:A[1]==="@"?Y:S}),i.removeAttribute(h)}else h.startsWith(g)&&(a.push({type:6,index:n}),i.removeAttribute(h));if($t.test(i.tagName)){let h=i.textContent.split(g),m=h.length-1;if(m>0){i.textContent=z?z.emptyScript:"";for(let _=0;_<m;_++)i.append(h[_],k()),v.nextNode(),a.push({type:2,index:++n});i.append(h[m],k())}}}else if(i.nodeType===8)if(i.data===gt)a.push({type:2,index:n});else{let h=-1;for(;(h=i.data.indexOf(g,h+1))!==-1;)a.push({type:7,index:n}),h+=g.length-1}n++}}static createElement(t,e){let s=b.createElement("template");return s.innerHTML=t,s}};function w(o,t,e=o,s){if(t===x)return t;let i=s!==void 0?e._$Co?.[s]:e._$Cl,n=O(t)?void 0:t._$litDirective$;return i?.constructor!==n&&(i?._$AO?.(!1),n===void 0?i=void 0:(i=new n(o),i._$AT(o,e,s)),s!==void 0?(e._$Co??=[])[s]=i:e._$Cl=i),i!==void 0&&(t=w(o,i._$AS(o,t.values),i,s)),t}var q=class{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){let{el:{content:e},parts:s}=this._$AD,i=(t?.creationScope??b).importNode(e,!0);v.currentNode=i;let n=v.nextNode(),r=0,p=0,a=s[0];for(;a!==void 0;){if(r===a.index){let c;a.type===2?c=new M(n,n.nextSibling,this,t):a.type===1?c=new a.ctor(n,a.name,a.strings,this,t):a.type===6&&(c=new G(n,this,t)),this._$AV.push(c),a=s[++p]}r!==a?.index&&(n=v.nextNode(),r++)}return v.currentNode=b,i}p(t){let e=0;for(let s of this._$AV)s!==void 0&&(s.strings!==void 0?(s._$AI(t,s,e),e+=s.strings.length-2):s._$AI(t[e])),e++}},M=class o{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,s,i){this.type=2,this._$AH=l,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=s,this.options=i,this._$Cv=i?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode,e=this._$AM;return e!==void 0&&t?.nodeType===11&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=w(this,t,e),O(t)?t===l||t==null||t===""?(this._$AH!==l&&this._$AR(),this._$AH=l):t!==this._$AH&&t!==x&&this._(t):t._$litType$!==void 0?this.$(t):t.nodeType!==void 0?this.T(t):jt(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==l&&O(this._$AH)?this._$AA.nextSibling.data=t:this.T(b.createTextNode(t)),this._$AH=t}$(t){let{values:e,_$litType$:s}=t,i=typeof s=="number"?this._$AC(t):(s.el===void 0&&(s.el=U.createElement(yt(s.h,s.h[0]),this.options)),s);if(this._$AH?._$AD===i)this._$AH.p(e);else{let n=new q(i,this),r=n.u(this.options);n.p(e),this.T(r),this._$AH=n}}_$AC(t){let e=_t.get(t.strings);return e===void 0&&_t.set(t.strings,e=new U(t)),e}k(t){Z(this._$AH)||(this._$AH=[],this._$AR());let e=this._$AH,s,i=0;for(let n of t)i===e.length?e.push(s=new o(this.O(k()),this.O(k()),this,this.options)):s=e[i],s._$AI(n),i++;i<e.length&&(this._$AR(s&&s._$AB.nextSibling,i),e.length=i)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){let s=ct(t).nextSibling;ct(t).remove(),t=s}}setConnected(t){this._$AM===void 0&&(this._$Cv=t,this._$AP?.(t))}},S=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,s,i,n){this.type=1,this._$AH=l,this._$AN=void 0,this.element=t,this.name=e,this._$AM=i,this.options=n,s.length>2||s[0]!==""||s[1]!==""?(this._$AH=Array(s.length-1).fill(new String),this.strings=s):this._$AH=l}_$AI(t,e=this,s,i){let n=this.strings,r=!1;if(n===void 0)t=w(this,t,e,0),r=!O(t)||t!==this._$AH&&t!==x,r&&(this._$AH=t);else{let p=t,a,c;for(t=n[0],a=0;a<n.length-1;a++)c=w(this,p[s+a],e,a),c===x&&(c=this._$AH[a]),r||=!O(c)||c!==this._$AH[a],c===l?t=l:t!==l&&(t+=(c??"")+n[a+1]),this._$AH[a]=c}r&&!i&&this.j(t)}j(t){t===l?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}},K=class extends S{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===l?void 0:t}},J=class extends S{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==l)}},Y=class extends S{constructor(t,e,s,i,n){super(t,e,s,i,n),this.type=5}_$AI(t,e=this){if((t=w(this,t,e,0)??l)===x)return;let s=this._$AH,i=t===l&&s!==l||t.capture!==s.capture||t.once!==s.once||t.passive!==s.passive,n=t!==l&&(s===l||i);i&&this.element.removeEventListener(this.name,this,s),n&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}},G=class{constructor(t,e,s){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=s}get _$AU(){return this._$AM._$AU}_$AI(t){w(this,t)}};var Wt=X.litHtmlPolyfillSupport;Wt?.(U,M),(X.litHtmlVersions??=[]).push("3.3.3");var vt=(o,t,e)=>{let s=e?.renderBefore??t,i=s._$litPart$;if(i===void 0){let n=e?.renderBefore??null;s._$litPart$=i=new M(t.insertBefore(k(),n),n,void 0,e??{})}return i._$AI(o),i};var tt=globalThis,$=class extends f{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){let e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=vt(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return x}};$._$litElement$=!0,$.finalized=!0,tt.litElementHydrateSupport?.({LitElement:$});var Ft=tt.litElementPolyfillSupport;Ft?.({LitElement:$});(tt.litElementVersions??=[]).push("4.2.2");var qt="0.1.0",et={sensor:{ph:"ph_sensor",orp:"orp_sensor",free_chlorine:"fc_sensor",water_temp:"sensor_temp",battery:"battery",ph_indicator:"ph_indicator",orp_indicator:"orp_indicator",chlorine_indicator:"chlorine_indicator",maintenance:"maintenance",ph_target:"ph_target",orp_target:"orp_target",refresh:"refresh_button"},salt:{power:"power_switch",chlorination:"chlorination_switch",salinity:"salinity",status:"salt_status",alarm:"salt_alarm",self_clean:"self_clean",water_temp:"salt_temp",time_remaining:"time_remaining",error_code:"salt_error"},pump:{pump:"pump_switch"}},Kt=Object.keys(et.salt),Jt=Object.keys(et.sensor);function Yt(o,t,e){let s=new Event(t,{bubbles:!0,composed:!0});s.detail=e,o.dispatchEvent(s)}function bt(o){let t={},e=o?.entities||{},s={};for(let[i,n]of Object.entries(e))n.platform==="intex_pool"&&(s[n.device_id||"_"]??=[]).push({eid:i,tk:n.translation_key});for(let i of Object.values(s)){let n="pump";i.some(r=>Kt.includes(r.tk))?n="salt":i.some(r=>Jt.includes(r.tk))&&(n="sensor");for(let{eid:r,tk:p}of i){let a=et[n]?.[p];a&&!t[a]&&(t[a]=r)}}return t}var N=class extends ${static getStubConfig(t){return{title:"Pool",...bt(t)}}static getConfigForm(){let t=s=>({selector:{entity:{domain:s,integration:"intex_pool"}}}),e=s=>({selector:{entity:{domain:s}}});return{schema:[{name:"title",selector:{text:{}}},{type:"expandable",title:"Water chemistry",schema:[{name:"ph_sensor",...t("sensor")},{name:"orp_sensor",...t("sensor")},{name:"fc_sensor",...t("sensor")},{name:"sensor_temp",...t("sensor")},{name:"battery",...t("sensor")},{name:"refresh_button",...t("button")}]},{type:"expandable",title:"Saltwater system",schema:[{name:"power_switch",...t("switch")},{name:"chlorination_switch",...t("switch")},{name:"salinity",...t("sensor")},{name:"salt_status",...t("sensor")},{name:"salt_alarm",...t("sensor")},{name:"self_clean",...t("select")},{name:"salt_temp",...t("sensor")},{name:"time_remaining",...t("sensor")}]},{type:"expandable",title:"Sand filter pump (any brand)",schema:[{name:"pump_switch",...e("switch")},{name:"pump_power",...e("sensor")},{name:"pump_energy",...e("sensor")},{name:"pump_temp",...e("sensor")}]}]}}setConfig(t){if(!t)throw new Error("Invalid configuration");this._config=t}set hass(t){this._hass=t,this.requestUpdate()}get hass(){return this._hass}getCardSize(){return 6}getGridOptions(){return{rows:6,columns:12,min_columns:6}}_roles(){return{...bt(this._hass),...this._config}}_st(t){return t?this._hass?.states?.[t]:void 0}_has(t){return!!this._st(t)}_num(t){let e=this._st(t),s=e?parseFloat(e.state):NaN;return Number.isFinite(s)?s:null}_on(t){return this._st(t)?.state==="on"}_name(t){return this._st(t)?.attributes?.friendly_name||t}_moreInfo(t){t&&Yt(this,"hass-more-info",{entityId:t})}_toggle(t){this._hass.callService("homeassistant","toggle",{entity_id:t})}_press(t){this._hass.callService("button","press",{entity_id:t})}_gauge(t,{min:e,max:s,unit:i,label:n,lo:r,hi:p,decimals:a=1}){let c=this._num(t),d=this._st(t),h=c==null?d?.state??"\u2014":c.toFixed(a),_=-120+(c==null?0:Math.max(0,Math.min(1,(c-e)/(s-e))))*240,A=c!=null&&(r==null||c>=r)&&(p==null||c<=p),xt=c==null?"var(--disabled-text-color)":A?"var(--success-color, #43a047)":"var(--warning-color, #ffa600)",R=40,At=50,wt=50,B=st=>[At+R*Math.cos((st-90)*Math.PI/180),wt+R*Math.sin((st-90)*Math.PI/180)],[St,Et]=B(-120),[Ct,Pt]=B(120),[kt,Ot]=B(_);return u`
      <button class="gauge" @click=${()=>this._moreInfo(t)} aria-label=${n}>
        <svg viewBox="0 0 100 78">
          <path d="M ${St} ${Et} A ${R} ${R} 0 1 1 ${Ct} ${Pt}" fill="none"
                stroke="var(--divider-color)" stroke-width="7" stroke-linecap="round"/>
          <circle cx=${kt} cy=${Ot} r="5.5" fill=${xt}/>
          <text x="50" y="48" class="g-val" fill="var(--primary-text-color)">${h}</text>
          <text x="50" y="62" class="g-unit" fill="var(--secondary-text-color)">${i??""}</text>
        </svg>
        <div class="g-label">${n}</div>
      </button>`}_chip(t,{label:e,icon:s}){let i=this._st(t);return i?u`
      <button class="chip" @click=${()=>this._moreInfo(t)}>
        ${s?u`<ha-icon icon=${s}></ha-icon>`:l}
        <span class="chip-label">${e}</span>
        <span class="chip-val">${i.state}</span>
      </button>`:l}_toggleBtn(t,e,s){if(!this._has(t))return l;let i=this._on(t);return u`
      <button class="toggle ${i?"on":""}" @click=${()=>this._toggle(t)}
              aria-pressed=${i} aria-label=${s}>
        <ha-icon icon=${e}></ha-icon>
        <span class="t-label">${s}</span>
        <span class="t-state">${i?"ON":"OFF"}</span>
      </button>`}render(){if(!this._hass||!this._config)return l;let t=this._roles(),e=["ph_sensor","orp_sensor","fc_sensor","sensor_temp","battery"].some(n=>this._has(t[n])),s=["power_switch","chlorination_switch","salinity","salt_status"].some(n=>this._has(t[n])),i=["pump_switch","pump_power","pump_energy","pump_temp"].some(n=>this._has(t[n]));return u`
      <ha-card>
        <div class="header">
          <ha-icon icon="mdi:pool"></ha-icon>
          <span class="title">${this._config.title??"Pool"}</span>
          ${this._headerStatus(t)}
        </div>
        <div class="body">
          ${e?this._chemistry(t):l}
          ${s?this._chlorinator(t):l}
          ${i?this._pump(t):l}
          ${!e&&!s&&!i?u`<div class="empty">No pool devices configured. Edit the card to link entities.</div>`:l}
        </div>
      </ha-card>`}_headerStatus(t){let e=this._st(t.salt_alarm),s=this._st(t.maintenance);return e&&e.state!=="normal"&&e.state!=="unknown"&&e.state!=="unavailable"?u`<span class="pill alarm">${e.attributes.friendly_name?.includes(":"),e.state}</span>`:s&&s.state==="red"?u`<span class="pill warn">Service</span>`:u`<span class="pill ok">OK</span>`}_chemistry(t){return u`
      <div class="section">
        <div class="section-head">Water chemistry
          ${this._has(t.refresh_button)?u`<button class="icon-btn" @click=${()=>this._press(t.refresh_button)} title="Refresh">
                     <ha-icon icon="mdi:refresh"></ha-icon></button>`:l}
        </div>
        <div class="gauges">
          ${this._has(t.ph_sensor)?this._gauge(t.ph_sensor,{min:6.8,max:8,unit:"pH",label:"pH",lo:7.2,hi:7.6,decimals:1}):l}
          ${this._has(t.orp_sensor)?this._gauge(t.orp_sensor,{min:400,max:900,unit:"mV",label:"ORP",lo:650,hi:750,decimals:0}):l}
          ${this._has(t.sensor_temp)?this._gauge(t.sensor_temp,{min:0,max:40,unit:"\xB0C",label:"Temp",lo:10,hi:35,decimals:1}):l}
        </div>
        <div class="chips">
          ${this._chip(t.fc_sensor,{label:"Free Cl",icon:"mdi:test-tube"})}
          ${this._chip(t.battery,{label:"Battery",icon:"mdi:battery"})}
        </div>
      </div>`}_chlorinator(t){let e=this._num(t.salinity),s=this._st(t.salt_status);return u`
      <div class="section">
        <div class="section-head">Saltwater system</div>
        <div class="toggles">
          ${this._toggleBtn(t.power_switch,"mdi:power","Power")}
          ${this._toggleBtn(t.chlorination_switch,"mdi:flash","Chlorine")}
        </div>
        <div class="chips">
          ${e!=null?u`<button class="chip" @click=${()=>this._moreInfo(t.salinity)}>
              <ha-icon icon="mdi:shaker-outline"></ha-icon><span class="chip-label">Salt</span>
              <span class="chip-val">${e} ppm</span></button>`:l}
          ${s?u`<button class="chip" @click=${()=>this._moreInfo(t.salt_status)}>
              <ha-icon icon="mdi:state-machine"></ha-icon><span class="chip-label">Status</span>
              <span class="chip-val">${s.state}</span></button>`:l}
          ${this._chip(t.salt_temp,{label:"Temp",icon:"mdi:thermometer"})}
          ${this._chip(t.time_remaining,{label:"Left",icon:"mdi:timer-sand"})}
          ${this._chip(t.self_clean,{label:"Clean",icon:"mdi:broom"})}
        </div>
      </div>`}_pump(t){return u`
      <div class="section">
        <div class="section-head">Sand filter pump</div>
        <div class="toggles">
          ${this._toggleBtn(t.pump_switch,"mdi:water-pump","Pump")}
        </div>
        <div class="chips">
          ${this._chip(t.pump_power,{label:"Power",icon:"mdi:flash"})}
          ${this._chip(t.pump_energy,{label:"Energy",icon:"mdi:lightning-bolt"})}
          ${this._chip(t.pump_temp,{label:"Water",icon:"mdi:thermometer"})}
        </div>
      </div>`}};D(N,"properties",{_config:{state:!0}}),D(N,"styles",j`
    ha-card { padding: 12px 14px 16px; }
    .header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
    .header ha-icon { color: var(--primary-color); }
    .title { font-size: 1.15rem; font-weight: 600; flex: 1; }
    .pill { font-size: .72rem; font-weight: 600; padding: 3px 10px; border-radius: 999px;
            color: var(--text-primary-color, #fff); white-space: nowrap; }
    .pill.ok { background: var(--success-color, #43a047); }
    .pill.warn { background: var(--warning-color, #ffa600); }
    .pill.alarm { background: var(--error-color, #db4437); }
    .section { padding: 10px 0; border-top: 1px solid var(--divider-color); }
    .section:first-of-type { border-top: none; }
    .section-head { display: flex; align-items: center; justify-content: space-between;
                    font-size: .78rem; font-weight: 600; text-transform: uppercase;
                    letter-spacing: .04em; color: var(--secondary-text-color); margin-bottom: 8px; }
    .gauges { display: grid; grid-template-columns: repeat(auto-fit, minmax(90px, 1fr)); gap: 6px; }
    .gauge { background: none; border: none; cursor: pointer; padding: 0; }
    .gauge svg { width: 100%; height: auto; }
    .g-val { font-size: 17px; font-weight: 700; text-anchor: middle; }
    .g-unit { font-size: 9px; text-anchor: middle; }
    .g-label { font-size: .72rem; color: var(--secondary-text-color); margin-top: -2px; }
    .chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
    .chip { display: inline-flex; align-items: center; gap: 5px; cursor: pointer;
            background: var(--secondary-background-color); border: none; border-radius: 999px;
            padding: 5px 11px; font-size: .82rem; color: var(--primary-text-color); }
    .chip ha-icon { --mdc-icon-size: 17px; color: var(--secondary-text-color); }
    .chip-label { color: var(--secondary-text-color); }
    .chip-val { font-weight: 600; }
    .toggles { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 8px; }
    .toggle { display: flex; flex-direction: column; align-items: center; gap: 2px; cursor: pointer;
              border: 1px solid var(--divider-color); border-radius: 14px; padding: 12px 8px;
              background: var(--card-background-color); color: var(--primary-text-color);
              transition: background .2s, color .2s, border-color .2s; }
    .toggle ha-icon { --mdc-icon-size: 26px; }
    .toggle .t-label { font-size: .82rem; font-weight: 600; }
    .toggle .t-state { font-size: .68rem; color: var(--secondary-text-color); }
    .toggle.on { background: var(--primary-color); color: var(--text-primary-color, #fff); border-color: var(--primary-color); }
    .toggle.on .t-state { color: var(--text-primary-color, #fff); opacity: .85; }
    .icon-btn { background: none; border: none; cursor: pointer; color: var(--secondary-text-color); padding: 2px; }
    .empty { padding: 18px 4px; color: var(--secondary-text-color); text-align: center; }
    @media (prefers-reduced-motion: reduce) { .toggle { transition: none; } }
  `);customElements.get("intex-pool-card")||customElements.define("intex-pool-card",N);window.customCards=window.customCards||[];window.customCards.push({type:"intex-pool-card",name:"Intex Pool",description:"Adaptive pool overview \u2014 chemistry, chlorinator and pump.",preview:!0,documentationURL:"https://github.com/Hovborg/intex-pool"});console.info(`%c INTEX-POOL-CARD %c v${qt} `,"color:#fff;background:#0288d1;font-weight:700;border-radius:3px 0 0 3px;padding:2px 4px","color:#0288d1;background:#fff;border-radius:0 3px 3px 0;padding:2px 4px");
/*! Bundled license information:

@lit/reactive-element/css-tag.js:
  (**
   * @license
   * Copyright 2019 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

@lit/reactive-element/reactive-element.js:
  (**
   * @license
   * Copyright 2017 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-html/lit-html.js:
  (**
   * @license
   * Copyright 2017 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-element/lit-element.js:
  (**
   * @license
   * Copyright 2017 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-html/is-server.js:
  (**
   * @license
   * Copyright 2022 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)
*/
