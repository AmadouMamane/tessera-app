import { chromium } from "playwright";
const b=await chromium.launch(); const p=await (await b.newContext({viewport:{width:1672,height:941},deviceScaleFactor:2})).newPage();
await p.goto("http://localhost:3390/fr/login",{waitUntil:"networkidle"});
await p.fill("#login-username","admin");await p.fill("#login-password","tessera-admin");
await p.click("button[type=submit]");await p.waitForTimeout(2200);
await p.goto("http://localhost:3390/fr/agent/synthese",{waitUntil:"networkidle"});await p.waitForTimeout(1500);
await p.screenshot({path:"/tmp/v2.png"});
await b.close();
