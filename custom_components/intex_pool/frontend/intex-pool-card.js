var Pt=Object.defineProperty;var Ot=(i,e,t)=>e in i?Pt(i,e,{enumerable:!0,configurable:!0,writable:!0,value:t}):i[e]=t;var E=(i,e,t)=>Ot(i,typeof e!="symbol"?e+"":e,t);var H=globalThis,z=H.ShadowRoot&&(H.ShadyCSS===void 0||H.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,V=Symbol(),lt=new WeakMap,k=class{constructor(e,t,s){if(this._$cssResult$=!0,s!==V)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o,t=this.t;if(z&&e===void 0){let s=t!==void 0&&t.length===1;s&&(e=lt.get(t)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),s&&lt.set(t,e))}return e}toString(){return this.cssText}},ct=i=>new k(typeof i=="string"?i:i+"",void 0,V),q=(i,...e)=>{let t=i.length===1?i[0]:e.reduce((s,r,o)=>s+(n=>{if(n._$cssResult$===!0)return n.cssText;if(typeof n=="number")return n;throw Error("Value passed to 'css' function must be a 'css' function result: "+n+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(r)+i[o+1],i[0]);return new k(t,i,V)},ht=(i,e)=>{if(z)i.adoptedStyleSheets=e.map(t=>t instanceof CSSStyleSheet?t:t.styleSheet);else for(let t of e){let s=document.createElement("style"),r=H.litNonce;r!==void 0&&s.setAttribute("nonce",r),s.textContent=t.cssText,i.appendChild(s)}},F=z?i=>i:i=>i instanceof CSSStyleSheet?(e=>{let t="";for(let s of e.cssRules)t+=s.cssText;return ct(t)})(i):i;var{is:Rt,defineProperty:Ut,getOwnPropertyDescriptor:Mt,getOwnPropertyNames:Nt,getOwnPropertySymbols:Tt,getPrototypeOf:Ht}=Object,D=globalThis,dt=D.trustedTypes,zt=dt?dt.emptyScript:"",Dt=D.reactiveElementPolyfillSupport,C=(i,e)=>i,W={toAttribute(i,e){switch(e){case Boolean:i=i?zt:null;break;case Object:case Array:i=i==null?i:JSON.stringify(i)}return i},fromAttribute(i,e){let t=i;switch(e){case Boolean:t=i!==null;break;case Number:t=i===null?null:Number(i);break;case Object:case Array:try{t=JSON.parse(i)}catch{t=null}}return t}},ut=(i,e)=>!Rt(i,e),pt={attribute:!0,type:String,converter:W,reflect:!1,useDefault:!1,hasChanged:ut};Symbol.metadata??=Symbol("metadata"),D.litPropertyMetadata??=new WeakMap;var _=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=pt){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){let s=Symbol(),r=this.getPropertyDescriptor(e,s,t);r!==void 0&&Ut(this.prototype,e,r)}}static getPropertyDescriptor(e,t,s){let{get:r,set:o}=Mt(this.prototype,e)??{get(){return this[t]},set(n){this[t]=n}};return{get:r,set(n){let c=r?.call(this);o?.call(this,n),this.requestUpdate(e,c,s)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??pt}static _$Ei(){if(this.hasOwnProperty(C("elementProperties")))return;let e=Ht(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(C("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(C("properties"))){let t=this.properties,s=[...Nt(t),...Tt(t)];for(let r of s)this.createProperty(r,t[r])}let e=this[Symbol.metadata];if(e!==null){let t=litPropertyMetadata.get(e);if(t!==void 0)for(let[s,r]of t)this.elementProperties.set(s,r)}this._$Eh=new Map;for(let[t,s]of this.elementProperties){let r=this._$Eu(t,s);r!==void 0&&this._$Eh.set(r,t)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let t=[];if(Array.isArray(e)){let s=new Set(e.flat(1/0).reverse());for(let r of s)t.unshift(F(r))}else e!==void 0&&t.push(F(e));return t}static _$Eu(e,t){let s=t.attribute;return s===!1?void 0:typeof s=="string"?s:typeof e=="string"?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,t=this.constructor.elementProperties;for(let s of t.keys())this.hasOwnProperty(s)&&(e.set(s,this[s]),delete this[s]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return ht(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,s){this._$AK(e,s)}_$ET(e,t){let s=this.constructor.elementProperties.get(e),r=this.constructor._$Eu(e,s);if(r!==void 0&&s.reflect===!0){let o=(s.converter?.toAttribute!==void 0?s.converter:W).toAttribute(t,s.type);this._$Em=e,o==null?this.removeAttribute(r):this.setAttribute(r,o),this._$Em=null}}_$AK(e,t){let s=this.constructor,r=s._$Eh.get(e);if(r!==void 0&&this._$Em!==r){let o=s.getPropertyOptions(r),n=typeof o.converter=="function"?{fromAttribute:o.converter}:o.converter?.fromAttribute!==void 0?o.converter:W;this._$Em=r;let c=n.fromAttribute(t,o.type);this[r]=c??this._$Ej?.get(r)??c,this._$Em=null}}requestUpdate(e,t,s,r=!1,o){if(e!==void 0){let n=this.constructor;if(r===!1&&(o=this[e]),s??=n.getPropertyOptions(e),!((s.hasChanged??ut)(o,t)||s.useDefault&&s.reflect&&o===this._$Ej?.get(e)&&!this.hasAttribute(n._$Eu(e,s))))return;this.C(e,t,s)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(e,t,{useDefault:s,reflect:r,wrapped:o},n){s&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,n??t??this[e]),o!==!0||n!==void 0)||(this._$AL.has(e)||(this.hasUpdated||s||(t=void 0),this._$AL.set(e,t)),r===!0&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(t){Promise.reject(t)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[r,o]of this._$Ep)this[r]=o;this._$Ep=void 0}let s=this.constructor.elementProperties;if(s.size>0)for(let[r,o]of s){let{wrapped:n}=o,c=this[r];n!==!0||this._$AL.has(r)||c===void 0||this.C(r,void 0,o,c)}}let e=!1,t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(s=>s.hostUpdate?.()),this.update(t)):this._$EM()}catch(s){throw e=!1,this._$EM(),s}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(t=>t.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(t=>this._$ET(t,this[t])),this._$EM()}updated(e){}firstUpdated(e){}};_.elementStyles=[],_.shadowRootOptions={mode:"open"},_[C("elementProperties")]=new Map,_[C("finalized")]=new Map,Dt?.({ReactiveElement:_}),(D.reactiveElementVersions??=[]).push("2.1.2");var Q=globalThis,ft=i=>i,L=Q.trustedTypes,mt=L?L.createPolicy("lit-html",{createHTML:i=>i}):void 0,vt="$lit$",g=`lit$${Math.random().toFixed(9).slice(2)}$`,xt="?"+g,Lt=`<${xt}>`,x=document,O=()=>x.createComment(""),R=i=>i===null||typeof i!="object"&&typeof i!="function",tt=Array.isArray,It=i=>tt(i)||typeof i?.[Symbol.iterator]=="function",K=`[ 	
\f\r]`,P=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,_t=/-->/g,gt=/>/g,y=RegExp(`>|${K}(?:([^\\s"'>=/]+)(${K}*=${K}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),$t=/'/g,bt=/"/g,At=/^(?:script|style|textarea|title)$/i,et=i=>(e,...t)=>({_$litType$:i,strings:e,values:t}),u=et(1),Qt=et(2),te=et(3),A=Symbol.for("lit-noChange"),l=Symbol.for("lit-nothing"),yt=new WeakMap,v=x.createTreeWalker(x,129);function wt(i,e){if(!tt(i)||!i.hasOwnProperty("raw"))throw Error("invalid template strings array");return mt!==void 0?mt.createHTML(e):e}var jt=(i,e)=>{let t=i.length-1,s=[],r,o=e===2?"<svg>":e===3?"<math>":"",n=P;for(let c=0;c<t;c++){let a=i[c],d,p,h=-1,f=0;for(;f<a.length&&(n.lastIndex=f,p=n.exec(a),p!==null);)f=n.lastIndex,n===P?p[1]==="!--"?n=_t:p[1]!==void 0?n=gt:p[2]!==void 0?(At.test(p[2])&&(r=RegExp("</"+p[2],"g")),n=y):p[3]!==void 0&&(n=y):n===y?p[0]===">"?(n=r??P,h=-1):p[1]===void 0?h=-2:(h=n.lastIndex-p[2].length,d=p[1],n=p[3]===void 0?y:p[3]==='"'?bt:$t):n===bt||n===$t?n=y:n===_t||n===gt?n=P:(n=y,r=void 0);let m=n===y&&i[c+1].startsWith("/>")?" ":"";o+=n===P?a+Lt:h>=0?(s.push(d),a.slice(0,h)+vt+a.slice(h)+g+m):a+g+(h===-2?c:m)}return[wt(i,o+(i[t]||"<?>")+(e===2?"</svg>":e===3?"</math>":"")),s]},U=class i{constructor({strings:e,_$litType$:t},s){let r;this.parts=[];let o=0,n=0,c=e.length-1,a=this.parts,[d,p]=jt(e,t);if(this.el=i.createElement(d,s),v.currentNode=this.el.content,t===2||t===3){let h=this.el.content.firstChild;h.replaceWith(...h.childNodes)}for(;(r=v.nextNode())!==null&&a.length<c;){if(r.nodeType===1){if(r.hasAttributes())for(let h of r.getAttributeNames())if(h.endsWith(vt)){let f=p[n++],m=r.getAttribute(h).split(g),b=/([.?@])?(.*)/.exec(f);a.push({type:1,index:o,name:b[2],strings:m,ctor:b[1]==="."?G:b[1]==="?"?X:b[1]==="@"?Y:S}),r.removeAttribute(h)}else h.startsWith(g)&&(a.push({type:6,index:o}),r.removeAttribute(h));if(At.test(r.tagName)){let h=r.textContent.split(g),f=h.length-1;if(f>0){r.textContent=L?L.emptyScript:"";for(let m=0;m<f;m++)r.append(h[m],O()),v.nextNode(),a.push({type:2,index:++o});r.append(h[f],O())}}}else if(r.nodeType===8)if(r.data===xt)a.push({type:2,index:o});else{let h=-1;for(;(h=r.data.indexOf(g,h+1))!==-1;)a.push({type:7,index:o}),h+=g.length-1}o++}}static createElement(e,t){let s=x.createElement("template");return s.innerHTML=e,s}};function w(i,e,t=i,s){if(e===A)return e;let r=s!==void 0?t._$Co?.[s]:t._$Cl,o=R(e)?void 0:e._$litDirective$;return r?.constructor!==o&&(r?._$AO?.(!1),o===void 0?r=void 0:(r=new o(i),r._$AT(i,t,s)),s!==void 0?(t._$Co??=[])[s]=r:t._$Cl=r),r!==void 0&&(e=w(i,r._$AS(i,e.values),r,s)),e}var J=class{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:t},parts:s}=this._$AD,r=(e?.creationScope??x).importNode(t,!0);v.currentNode=r;let o=v.nextNode(),n=0,c=0,a=s[0];for(;a!==void 0;){if(n===a.index){let d;a.type===2?d=new M(o,o.nextSibling,this,e):a.type===1?d=new a.ctor(o,a.name,a.strings,this,e):a.type===6&&(d=new Z(o,this,e)),this._$AV.push(d),a=s[++c]}n!==a?.index&&(o=v.nextNode(),n++)}return v.currentNode=x,r}p(e){let t=0;for(let s of this._$AV)s!==void 0&&(s.strings!==void 0?(s._$AI(e,s,t),t+=s.strings.length-2):s._$AI(e[t])),t++}},M=class i{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,s,r){this.type=2,this._$AH=l,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=s,this.options=r,this._$Cv=r?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,t=this._$AM;return t!==void 0&&e?.nodeType===11&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=w(this,e,t),R(e)?e===l||e==null||e===""?(this._$AH!==l&&this._$AR(),this._$AH=l):e!==this._$AH&&e!==A&&this._(e):e._$litType$!==void 0?this.$(e):e.nodeType!==void 0?this.T(e):It(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==l&&R(this._$AH)?this._$AA.nextSibling.data=e:this.T(x.createTextNode(e)),this._$AH=e}$(e){let{values:t,_$litType$:s}=e,r=typeof s=="number"?this._$AC(e):(s.el===void 0&&(s.el=U.createElement(wt(s.h,s.h[0]),this.options)),s);if(this._$AH?._$AD===r)this._$AH.p(t);else{let o=new J(r,this),n=o.u(this.options);o.p(t),this.T(n),this._$AH=o}}_$AC(e){let t=yt.get(e.strings);return t===void 0&&yt.set(e.strings,t=new U(e)),t}k(e){tt(this._$AH)||(this._$AH=[],this._$AR());let t=this._$AH,s,r=0;for(let o of e)r===t.length?t.push(s=new i(this.O(O()),this.O(O()),this,this.options)):s=t[r],s._$AI(o),r++;r<t.length&&(this._$AR(s&&s._$AB.nextSibling,r),t.length=r)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){let s=ft(e).nextSibling;ft(e).remove(),e=s}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},S=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,s,r,o){this.type=1,this._$AH=l,this._$AN=void 0,this.element=e,this.name=t,this._$AM=r,this.options=o,s.length>2||s[0]!==""||s[1]!==""?(this._$AH=Array(s.length-1).fill(new String),this.strings=s):this._$AH=l}_$AI(e,t=this,s,r){let o=this.strings,n=!1;if(o===void 0)e=w(this,e,t,0),n=!R(e)||e!==this._$AH&&e!==A,n&&(this._$AH=e);else{let c=e,a,d;for(e=o[0],a=0;a<o.length-1;a++)d=w(this,c[s+a],t,a),d===A&&(d=this._$AH[a]),n||=!R(d)||d!==this._$AH[a],d===l?e=l:e!==l&&(e+=(d??"")+o[a+1]),this._$AH[a]=d}n&&!r&&this.j(e)}j(e){e===l?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}},G=class extends S{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===l?void 0:e}},X=class extends S{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==l)}},Y=class extends S{constructor(e,t,s,r,o){super(e,t,s,r,o),this.type=5}_$AI(e,t=this){if((e=w(this,e,t,0)??l)===A)return;let s=this._$AH,r=e===l&&s!==l||e.capture!==s.capture||e.once!==s.once||e.passive!==s.passive,o=e!==l&&(s===l||r);r&&this.element.removeEventListener(this.name,this,s),o&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},Z=class{constructor(e,t,s){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=s}get _$AU(){return this._$AM._$AU}_$AI(e){w(this,e)}};var Bt=Q.litHtmlPolyfillSupport;Bt?.(U,M),(Q.litHtmlVersions??=[]).push("3.3.3");var St=(i,e,t)=>{let s=t?.renderBefore??e,r=s._$litPart$;if(r===void 0){let o=t?.renderBefore??null;s._$litPart$=r=new M(e.insertBefore(O(),o),o,void 0,t??{})}return r._$AI(i),r};var st=globalThis,$=class extends _{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=St(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return A}};$._$litElement$=!0,$.finalized=!0,st.litElementHydrateSupport?.({LitElement:$});var Vt=st.litElementPolyfillSupport;Vt?.({LitElement:$});(st.litElementVersions??=[]).push("4.2.2");var qt="0.19.1",Ft={light:{"--primary-color":"#0078a8","--primary-text-color":"#16202a","--secondary-text-color":"#5b6b78","--card-background-color":"#ffffff","--ha-card-background":"#ffffff","--secondary-background-color":"#eef3f7","--divider-color":"#e1e8ee","--success-color":"#1e7d4f","--warning-color":"#a66200","--error-color":"#b83224","--text-primary-color":"#ffffff"},dark:{"--primary-color":"#23b5f0","--primary-text-color":"#e9eef2","--secondary-text-color":"#9aa7b2","--card-background-color":"#1b2228","--ha-card-background":"#1b2228","--secondary-background-color":"#252e36","--divider-color":"#333d46","--success-color":"#37c98a","--warning-color":"#f5b342","--error-color":"#ec6a55","--text-primary-color":"#06222f"},ocean:{"--primary-color":"#2bd4c7","--primary-text-color":"#e7f3f8","--secondary-text-color":"#8fb3c2","--card-background-color":"#0e2230","--ha-card-background":"linear-gradient(155deg, #0c3145, #071620)","--secondary-background-color":"rgba(255,255,255,.07)","--divider-color":"rgba(255,255,255,.10)","--success-color":"#34e0b0","--warning-color":"#ffc24b","--error-color":"#ff7a66","--text-primary-color":"#04202a"},midnight:{"--primary-color":"#7aa2ff","--primary-text-color":"#e4e9f2","--secondary-text-color":"#8b93a7","--card-background-color":"#11151c","--ha-card-background":"linear-gradient(160deg, #161b26, #0a0d13)","--secondary-background-color":"#1c2230","--divider-color":"#2a3140","--success-color":"#56d99a","--warning-color":"#f3b94f","--error-color":"#f0736a","--text-primary-color":"#0a0d13"}},j={sensor:{ph:"ph_sensor",orp:"orp_sensor",free_chlorine:"fc_sensor",water_temp:"sensor_temp",battery:"battery",ph_indicator:"ph_indicator",orp_indicator:"orp_indicator",refresh:"refresh_button",orp_trend:"orp_trend",last_measurement:"last_measurement"},salt:{power:"power_switch",chlorination:"chlorination_switch",salinity:"salinity",status:"salt_status",alarm:"salt_alarm",water_temp:"salt_temp",schedules:"schedules_sensor"},pump:{pump:"pump_switch"}};function Wt(){let i=Object.keys(j),e={};for(let t of i){let s=new Set(Object.keys(j[t]));for(let r of i)if(r!==t)for(let o of Object.keys(j[r]))s.delete(o);e[t]=s}return e}var Et=Wt(),I=null;function kt(i){let e=i?.entities||{};if(I&&I.ref===e)return I.result;let t={},s={};for(let[r,o]of Object.entries(e))o.platform==="intex_pool"&&(s[o.device_id||"_"]??=[]).push({eid:r,tk:o.translation_key});for(let r of Object.values(s)){let o="pump";r.some(n=>Et.salt.has(n.tk))?o="salt":r.some(n=>Et.sensor.has(n.tk))&&(o="sensor");for(let{eid:n,tk:c}of r){let a=j[o]?.[c];a&&!t[a]&&(t[a]=n)}}return I={ref:e,result:t},t}var N=class extends ${constructor(){super(...arguments);E(this,"_busy",new Set);E(this,"_staleTimer",null)}connectedCallback(){super.connectedCallback(),this._staleTimer=setInterval(()=>this.requestUpdate(),5*60*1e3)}disconnectedCallback(){super.disconnectedCallback(),clearInterval(this._staleTimer),this._staleTimer=null}static getStubConfig(t){return{...kt(t)}}static getConfigForm(){let t=r=>({selector:{entity:{domain:r,integration:"intex_pool"}}}),s=r=>({selector:{entity:{domain:r}}});return{schema:[{name:"title",selector:{text:{}}},{name:"variant",selector:{select:{mode:"dropdown",options:[{value:"auto",label:"Auto (follow Home Assistant theme)"},{value:"light",label:"Light"},{value:"dark",label:"Dark"},{value:"ocean",label:"Ocean (dark teal)"},{value:"midnight",label:"Midnight (deep dark)"}]}}},{type:"expandable",name:"water_chemistry",title:"Water chemistry",schema:[{name:"ph_sensor",...t("sensor")},{name:"orp_sensor",...t("sensor")},{name:"fc_sensor",...t("sensor")},{name:"sensor_temp",...t("sensor")},{name:"battery",...t("sensor")},{name:"refresh_button",...t("button")},{name:"orp_trend",...t("sensor")},{name:"last_measurement",...t("sensor")}]},{type:"expandable",name:"salt_system",title:"Saltwater system",schema:[{name:"power_switch",...t("switch")},{name:"chlorination_switch",...t("switch")},{name:"salinity",...t("sensor")},{name:"salt_status",...t("sensor")},{name:"salt_alarm",...t("sensor")},{name:"salt_temp",...t("sensor")},{name:"schedules_sensor",...t("sensor")}]},{type:"expandable",name:"pump",title:"Sand filter pump (any brand)",schema:[{name:"pump_switch",...s("switch")}]}]}}setConfig(t){if(!t)throw new Error("Invalid configuration");this._config=t}set hass(t){this._hass=t,this.requestUpdate()}get hass(){return this._hass}getCardSize(){return 3}getGridOptions(){return{rows:3,columns:12,min_columns:6}}_paletteStyle(){let t=Ft[this._config?.variant];return t?Object.entries(t).map(([s,r])=>`${s}:${r}`).join(";"):""}_roles(){return{...kt(this._hass),...this._config}}_st(t){return t?this._hass?.states?.[t]:void 0}_has(t){let s=this._st(t);return!!s&&s.state!=="unavailable"}_num(t){let s=this._st(t),r=s?parseFloat(s.state):NaN;return Number.isFinite(r)?r:null}_on(t){return this._st(t)?.state==="on"}_fmt(t){try{return this._hass.formatEntityState(t)}catch{return t.state}}_moreInfo(t){t&&rt(this,"hass-more-info",{entityId:t})}_toggle(t){this._busy.has(t)||(this._busy.add(t),this.requestUpdate(),this._hass.callService("homeassistant","toggle",{entity_id:t}).catch(s=>{console.error("[intex-pool-card] toggle failed:",s),rt(this,"hass-notification",{message:`Toggle failed: ${s?.message??s}`})}).finally(()=>{this._busy.delete(t),this.requestUpdate()}))}_press(t){this._busy.has(t)||(this._busy.add(t),this.requestUpdate(),this._hass.callService("button","press",{entity_id:t}).catch(s=>{console.error("[intex-pool-card] press failed:",s),rt(this,"hass-notification",{message:`Press failed: ${s?.message??s}`})}).finally(()=>{this._busy.delete(t),this.requestUpdate()}))}_indicatorCls(t){if(!t)return null;let s=this._st(t);if(!s||s.state==="unavailable")return null;let r=s.state.toLowerCase();return r==="green"?"good":r==="yellow"?"warn":r==="red"||r==="saltwater_abnormal"?"bad":null}_ageText(t){if(!t)return null;let s=this._st(t);if(!s||s.state==="unavailable"||s.state==="unknown")return null;let r=Date.parse(s.state);if(!Number.isFinite(r))return null;let o=Date.now()-r;if(o<0)return null;let n=Math.floor(o/6e4);if(n<60)return`${n}m`;let c=Math.floor(n/60);return c<48?`${c}h`:`${Math.floor(c/24)}d`}_staleBadge(t){if(!t)return l;let s=this._st(t);if(!s||s.state==="unavailable"||s.state==="unknown")return l;let r=Date.parse(s.state);if(!Number.isFinite(r))return l;if(Date.now()-r<3*60*60*1e3)return l;let n=this._ageText(t)??"?",c=`Last measurement: ${n} ago \u2014 readings may be outdated`;return u`<span class="stale-badge" title=${c} aria-label=${c}>
      <span class="stale-dot"></span><span class="stale-age">${n}</span>
    </span>`}_tile(t,{label:s,digits:r=0,lo:o,hi:n,unit:c,indicatorId:a,orpTrendId:d}={}){let p=this._st(t);if(!p)return l;let h=this._num(t),f=h==null?p.state??"\u2014":h.toFixed(r),m=h==null?null:(o==null||h>=o)&&(n==null||h<=n),b=this._indicatorCls(a),B;b!==null?B=b:B=m===null?"":m?"good":"warn";let Ct=`${s}: ${f}${c?" "+c:""}`,it=l;if(d){let T=this._st(d);if(T&&T.state!=="unavailable"&&T.state!=="unknown"){let ot=T.state.toLowerCase(),nt={low:.45,mid:.7,high:1}[ot];if(nt!=null){let at=`ORP trend: ${ot}`;it=u`<sup class="orp-trend" style="opacity:${nt}"
            title=${at} aria-label=${at}>▴</sup>`}}}return u`
      <button class="tile" aria-label=${Ct} @click=${()=>this._moreInfo(t)}>
        <div class="v">${f}${c?u`<span class="u">${c}</span>`:l}${it}</div>
        <div class="l">${s}</div>
        <div class="bar ${B}"></div>
      </button>`}_ctrl(t,s,r,o=!1){if(!this._has(t))return l;let n=o?!1:this._on(t),c=this._busy.has(t);return u`
      <button class="pill ${n?"on":""} ${c?"busy":""}"
        aria-label=${r} aria-pressed=${n}
        ?disabled=${c}
        @click=${()=>o?this._press(t):this._toggle(t)}>
        <ha-icon icon=${s}></ha-icon><span>${r}</span>
      </button>`}_statusPill(t){let s=this._st(t.salt_alarm);if(s&&!["normal","unknown","unavailable","e93"].includes(s.state))return u`<span class="status alarm">${this._fmt(s)}</span>`;let r=this._st(t.salt_status);return r&&this._has(t.salt_status)?u`<span class="status ok">${this._fmt(r)}</span>`:t.salt_alarm||t.salt_status?u`<span class="status off">Offline</span>`:u`<span class="status ok">OK</span>`}render(){if(!this._hass||!this._config)return l;let t=this._roles(),s=this._has(t.sensor_temp)?t.sensor_temp:t.salt_temp,r=[this._has(t.ph_sensor)?this._tile(t.ph_sensor,{label:"pH",digits:1,lo:7.2,hi:7.6,indicatorId:t.ph_indicator}):l,this._has(t.orp_sensor)?this._tile(t.orp_sensor,{label:"ORP",unit:"mV",lo:650,hi:750,indicatorId:t.orp_indicator,orpTrendId:t.orp_trend}):l,this._has(t.fc_sensor)?this._tile(t.fc_sensor,{label:"Cl\u2082",digits:2,unit:"ppm",lo:1,hi:3}):l,this._has(s)?this._tile(s,{label:"Temp",digits:1,unit:"\xB0",lo:10,hi:35}):l,this._has(t.salinity)?this._tile(t.salinity,{label:"Salt",lo:800,hi:1800}):l].filter(d=>d!==l),o=[this._ctrl(t.power_switch,"mdi:power","Power"),this._ctrl(t.chlorination_switch,"mdi:flash","Chlorine"),this._ctrl(t.pump_switch,"mdi:water-pump","Pump")].filter(d=>d!==l),n=this._has(t.battery),c=this._has(t.refresh_button),a=r.length===0&&o.length===0;return u`
      <ha-card style=${this._paletteStyle()}>
        <div class="head">
          <ha-icon class="logo" icon="mdi:pool"></ha-icon>
          <span class="title">${this._config.title??"Pool"}</span>
          ${this._statusPill(t)}
        </div>
        ${a?u`<div class="empty">No pool devices. Edit the card to select entities.</div>`:u`
            ${r.length?u`<div class="metrics">${r}</div>`:l}
            ${o.length||n||c?u`<div class="ctrls">
                  ${o}
                  <span class="spacer"></span>
                  ${n?u`<button class="mini" aria-label="Battery"
                        @click=${()=>this._moreInfo(t.battery)} title="Battery">
                        <ha-icon icon="mdi:battery"></ha-icon>${this._num(t.battery)??"?"}%</button>`:l}
                  ${this._staleBadge(t.last_measurement)}
                  ${c?u`<button class="mini" @click=${()=>this._press(t.refresh_button)} title="Refresh measurement">
                        <ha-icon icon="mdi:refresh"></ha-icon></button>`:l}
                </div>`:l}
            ${this._scheduleSection(t)}`}
      </ha-card>`}_scheduleSection(t){let r=this._st(t.schedules_sensor)?.attributes?.schedules||[];return r.length?u`
      <div class="sched" @click=${()=>this._moreInfo(t.schedules_sensor)}>
        <div class="sched-head">
          <ha-icon icon="mdi:calendar-clock"></ha-icon><span>Schedules</span>
          <span class="sched-count">${r.length}</span>
        </div>
        ${r.map(o=>u`<div class="sched-row">${o}</div>`)}
      </div>`:l}};E(N,"properties",{_config:{state:!0}}),E(N,"styles",q`
    ha-card { padding: 12px 14px; }
    .head { display: flex; align-items: center; gap: 8px; }
    .logo {
      --mdc-icon-size: 22px; color: var(--text-primary-color, #fff);
      background: var(--primary-color); border-radius: 9px; padding: 4px;
      box-sizing: content-box; width: 22px; height: 22px;
    }
    .title { font-size: 1.05rem; font-weight: 600; flex: 1; letter-spacing: .01em; }
    .status {
      font-size: .7rem; font-weight: 600; padding: 3px 9px; border-radius: 999px;
      color: var(--text-primary-color, #fff); white-space: nowrap; max-width: 50%;
      overflow: hidden; text-overflow: ellipsis;
    }
    .status.ok { background: var(--success-color, #2e9e5b); }
    .status.warn { background: var(--warning-color, #f5a300); }
    .status.alarm { background: var(--error-color, #db4437); }
    .status.off { background: var(--disabled-text-color, #757575); }

    .metrics {
      display: grid; grid-template-columns: repeat(auto-fit, minmax(56px, 1fr));
      gap: 6px; margin-top: 12px;
    }
    .tile {
      position: relative; border: none; cursor: pointer; padding: 9px 4px 8px;
      border-radius: 13px; background: var(--secondary-background-color);
      color: var(--primary-text-color); text-align: center; overflow: hidden;
      transition: transform .12s ease;
    }
    .tile:hover { transform: translateY(-1px); }
    .tile .v { font-size: 1.12rem; font-weight: 700; line-height: 1.1; }
    .tile .v .u { font-size: .62rem; font-weight: 600; margin-left: 1px; opacity: .65; }
    .tile .l {
      font-size: .6rem; font-weight: 600; text-transform: uppercase;
      letter-spacing: .06em; color: var(--secondary-text-color); margin-top: 2px;
    }
    .tile .bar { position: absolute; left: 22%; right: 22%; bottom: 0; height: 3px;
      border-radius: 3px 3px 0 0; background: transparent; }
    .tile .bar.good { background: var(--success-color, #2e9e5b); }
    .tile .bar.warn { background: var(--warning-color, #f5a300); }
    .tile .bar.bad  { background: var(--error-color, #db4437); }

    /* Feature 1 — ORP trend superscript marker */
    .orp-trend {
      font-size: .55rem; font-weight: 700; margin-left: 2px;
      vertical-align: super; line-height: 1; color: var(--primary-color);
      transition: opacity .2s;
    }

    .ctrls { display: flex; align-items: center; gap: 6px; margin-top: 12px; flex-wrap: wrap; }
    .spacer { flex: 1; }
    .pill {
      display: inline-flex; align-items: center; gap: 5px; cursor: pointer;
      padding: 6px 12px 6px 9px; border-radius: 999px; font-size: .8rem; font-weight: 600;
      border: 1.5px solid var(--divider-color); background: var(--card-background-color);
      color: var(--primary-text-color); transition: background .18s, color .18s, border-color .18s;
    }
    .pill ha-icon { --mdc-icon-size: 18px; }
    .pill.on { background: var(--primary-color); color: var(--text-primary-color, #fff); border-color: var(--primary-color); }
    .pill.busy, .pill:disabled { opacity: .45; cursor: not-allowed; pointer-events: none; }
    .mini {
      display: inline-flex; align-items: center; gap: 3px; cursor: pointer; border: none;
      background: none; color: var(--secondary-text-color); font-size: .78rem; font-weight: 600; padding: 4px;
    }
    .mini ha-icon { --mdc-icon-size: 17px; }

    /* Feature 2 — stale-measurement badge */
    .stale-badge {
      display: inline-flex; align-items: center; gap: 3px;
      color: var(--warning-color, #f5a300); font-size: .72rem; font-weight: 600;
    }
    .stale-dot {
      display: inline-block; width: 6px; height: 6px; border-radius: 50%;
      background: var(--warning-color, #f5a300); flex-shrink: 0;
    }
    .stale-age { line-height: 1; }

    .sched { margin-top: 12px; padding-top: 9px; border-top: 1px solid var(--divider-color); cursor: pointer; }
    .sched-head { display: flex; align-items: center; gap: 6px; font-size: .72rem; font-weight: 600;
      text-transform: uppercase; letter-spacing: .05em; color: var(--secondary-text-color); margin-bottom: 5px; }
    .sched-head ha-icon { --mdc-icon-size: 16px; }
    .sched-count { margin-left: auto; background: var(--secondary-background-color);
      border-radius: 999px; padding: 1px 9px; color: var(--primary-text-color); }
    .sched-row { font-size: .82rem; line-height: 1.5; padding-left: 22px; color: var(--primary-text-color); }
    .empty { padding: 14px 2px; color: var(--secondary-text-color); text-align: center; font-size: .85rem; }
    @media (prefers-reduced-motion: reduce) { .tile, .pill { transition: none; } }
  `);function rt(i,e,t){let s=new Event(e,{bubbles:!0,composed:!0});s.detail=t,i.dispatchEvent(s)}customElements.get("intex-pool-card")||customElements.define("intex-pool-card",N);window.customCards=window.customCards||[];window.customCards.push({type:"intex-pool-card",name:"Intex Pool",description:"Kompakt pool-kort \u2014 kemi, klorinator og pumpe.",preview:!0,documentationURL:"https://github.com/Hovborg/intex-pool"});console.info(`%c INTEX-POOL-CARD %c v${qt} `,"color:#fff;background:#0288d1;font-weight:700;border-radius:3px 0 0 3px;padding:2px 4px","color:#0288d1;background:#fff;border-radius:0 3px 3px 0;padding:2px 4px");
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
//# sourceMappingURL=intex-pool-card.js.map
