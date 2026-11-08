import { chromium } from 'playwright'; import fs from 'fs';
const U='http://127.0.0.1:3000', A='http://127.0.0.1:8000/api/v1', S='/Users/sunqinyue/Documents/work/BJDEV/claude/ai-video-platform/docs/ui-simplification-2026-11-08/p1-after/';
const out={trial:{clicks:[],decisions:[]},key:{clicks:[],decisions:[]},checks:{}};
const br=await chromium.launch();
async function newUser(tag){const ctx=await br.newContext({viewport:{width:1440,height:900},acceptDownloads:true});const p=await ctx.newPage();
 p.on('pageerror',e=>console.log('PAGEERROR',e.message));let native=0;p.on('dialog',d=>{native++;d.accept()});
 const user=tag+Date.now()%1e6,pw='Ux-Test-2026!';await p.goto(U+'/register',{waitUntil:'networkidle'});
 await p.getByPlaceholder('请输入用户名').fill(user);await p.getByPlaceholder('请输入邮箱').fill(user+'@example.test');await p.getByPlaceholder('请输入密码（至少6位）').fill(pw);await p.getByPlaceholder('请再次输入密码').fill(pw);
 return {ctx,p,user,native:()=>native};}
const shot=async(p,n,full=false)=>{await p.waitForTimeout(700);await p.screenshot({path:S+n+'.png',fullPage:full});console.log('shot',n)};
const vis=async(p)=>p.evaluate(()=>{const v=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0};const m=document.querySelector('main')||document.body;return {controls:[...m.querySelectorAll('input:not([type=hidden]),textarea,select')].filter(v).length,buttons:[...m.querySelectorAll('button')].filter(v).length}});
// ---------- TRIAL ----------
if(!process.env.ONLY_KEY){const {ctx,p,user,native}=await newUser('p0t');const T=out.trial;const C=n=>T.clicks.push(n);
 await p.getByTestId('register-accept-terms').check().catch(()=>p.getByTestId('register-accept-terms').click());C('勾选条款');
 await p.locator('button[type=submit]').click();C('注册');await p.waitForURL(/llm-config/,{timeout:20000});await p.waitForLoadState('networkidle');await p.waitForTimeout(1500);
 out.checks.welcomeUrl=p.url();out.checks.welcomeControls=await vis(p);out.checks.choiceButtons=await p.getByTestId('onboarding-choice').getByRole('button').count();await shot(p,'01-welcome-two-choices');
 T.decisions.push('免费试用 还是 我有 Key');
 await p.getByTestId('onboarding-choice').getByRole('button',{name:/免费试用/}).click();C('免费试用');
 await p.waitForURL(/\/novels\?start=paste/,{timeout:120000});await p.waitForLoadState('networkidle');await p.waitForTimeout(1200);
 out.checks.pasteFocused=await p.getByTestId('novel-paste-input').evaluate(e=>document.activeElement===e);await shot(p,'02-novels-paste-box');
 await p.getByTestId('novel-paste-input').fill(fs.readFileSync('novel-multi.txt','utf8'));await shot(p,'03-pasted');
 await p.getByTestId('novel-paste-parse').click();C('识别章节');await p.getByRole('button',{name:'确认导入'}).waitFor({timeout:30000});
 out.checks.autoTitle=await p.getByPlaceholder('导入后小说标题').inputValue();await shot(p,'04-paste-preview-auto-title');
 await p.getByRole('button',{name:'确认导入'}).click();C('确认导入');await p.waitForURL(u=>/\/novels\/[0-9a-f-]{36}/.test(u.pathname),{timeout:30000});await p.waitForLoadState('networkidle');await p.waitForTimeout(2000);
 out.checks.detailControls=await vis(p);out.checks.detailHasAiNext=await p.getByText('AI 下一步').count();out.checks.detailGenScriptBtns=await p.getByRole('button',{name:/生成剧本/}).count();
 out.checks.detailDeterministic=(await p.locator('main').first().innerText()).includes('Deterministic');await shot(p,'05-novel-detail-one-entry',true);
 await p.getByTestId('novel-more-actions').click();await p.waitForTimeout(500);await shot(p,'06-more-menu-step-mode');await p.keyboard.press('Escape');
 await p.getByRole('tab',{name:/^角色/}).waitFor();out.checks.tabsDefault=await p.getByRole('tab').allInnerTexts();await shot(p,'06b-two-tabs');
 await p.getByTestId('one-click-generate').click();C('一键生成视频（试用无需确认）');await p.waitForTimeout(800);out.checks.confirmDialogs=await p.getByRole('alertdialog').count()+await p.getByRole('dialog').count();
 const card=p.getByTestId('pipeline-status-card');await card.waitFor();const t0=Date.now();let last='';
 for(;;){const x=(await card.innerText()).split('\n')[0];if(x!==last){console.log(((Date.now()-t0)/1000|0)+'s',x);last=x}if(/已完成|需处理|已取消/.test(x))break;if(Date.now()-t0>900000)throw new Error('timeout');await p.waitForTimeout(4000);}
 out.checks.genStatus=last;out.checks.genSeconds=(Date.now()-t0)/1000|0;await card.scrollIntoViewIfNeeded();await shot(p,'08-finished-player');
 const v=p.getByTestId('pipeline-final-video');out.checks.duration=await v.evaluate(async el=>{if(isNaN(el.duration))await new Promise(r=>{el.onloadedmetadata=r;setTimeout(r,8000)});return el.duration});
 out.checks.phases=await p.getByTestId('pipeline-phases').innerText().catch(()=>null);C('播放（播放器内）');
 const href=await p.getByRole('link',{name:'下载视频'}).getAttribute('href');C('下载视频');const r=await ctx.request.get(href);const buf=await r.body();out.checks.download={bytes:buf.length,type:r.headers()['content-type'],disp:r.headers()['content-disposition']};
 await p.getByRole('link',{name:'查看发布'}).click();C('查看发布');await p.waitForLoadState('networkidle');await p.waitForTimeout(2500);out.checks.publishUrl=p.url();await shot(p,'09-publication');
 await p.goto(U+'/synthesis',{waitUntil:'networkidle'});await shot(p,'10-synthesis-my-videos',true);
 await p.goto(U+'/novels/new',{waitUntil:'networkidle'});out.checks.newNovelControls=await vis(p);await shot(p,'11-novel-new-simple',true);
 await p.goto(U+'/llm-config?section=overview',{waitUntil:'networkidle'});await p.waitForTimeout(1500);await shot(p,'12-model-center-overview',true);
 await p.goto(U+'/llm-config?section=connections',{waitUntil:'networkidle'});await p.waitForTimeout(1500);out.checks.mcConnText=(await p.locator('main').first().innerText()).match(/live-|contract-|[0-9a-f]{8}-[0-9a-f]{4}-/g);await shot(p,'13-model-center-connections',true);
 await p.goto(U+'/llm-config?section=catalog',{waitUntil:'networkidle'});await p.waitForTimeout(1500);out.checks.mcCatalogText=(await p.locator('main').first().innerText()).match(/live-|contract-|[0-9a-f]{8}-[0-9a-f]{4}-/g);await shot(p,'14-model-center-catalog',true);
 await p.getByTestId('model-center-pro-toggle').click();await p.waitForTimeout(500);await shot(p,'15-model-center-pro-on');
 out.trial.native=native();out.trial.user=user;await ctx.close();}
fs.writeFileSync(process.env.ONLY_KEY?'p1-key.json':'p1.json',JSON.stringify(out,null,1));console.log(JSON.stringify(out,null,1));await br.close();
