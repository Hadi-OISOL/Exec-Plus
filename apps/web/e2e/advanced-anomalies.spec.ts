/* Use case: Exercises private rolling and combination checks through actual UI and backend.
What it does: Verifies evidence, review, downloads, narrow layouts and clearing protected reads. */
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { finishInitialReview } from "./workspace-helpers";

for (const method of ["rolling", "multivariate"] as const) test(`${method} analyses retain exact evidence and clear denied reads`, async ({ page }) => {
  test.setTimeout(180_000);
  const token=execFileSync("python3",["-m","execplus.manage","provision-user","--email",`advanced-${randomUUID()}@example.test`],{cwd:"../..",encoding:"utf8"}).trim();
  const headers={Authorization:`Bearer ${token}`}; const errors:string[]=[];
  page.on("pageerror",error=>errors.push(error.message));
  const csv=method==="rolling"?"day,region,amount\n"+Array.from({length:49},(_,i)=>`${new Date(Date.UTC(2020,0,1+i)).toISOString().slice(0,10)},North,${i===28?1000:10}`).join("\n")+"\n":
    "id,cohort,a,b\n"+Array.from({length:70},(_,i)=>`r${i},${i<60?"reference":"comparison"},${(i*3+i*i)%41},${i<65?(i*11+i*i*2)%41:10000}`).join("\n")+"\n";
  await page.goto("/workspace");await page.getByLabel("Session token").fill(token);await page.getByRole("button",{name:"Sign in",exact:true}).click();
  await page.getByLabel("CSV or Excel file").setInputFiles({name:`${method}.csv`,mimeType:"text/csv",buffer:Buffer.from(csv)});
  await page.getByRole("button",{name:"Upload file",exact:true}).click();await finishInitialReview(page);
  const wid=await page.getByLabel("Current workspace").inputValue(),did=await page.getByLabel("Dataset",{exact:true}).inputValue(),uid=await page.getByLabel("Profile upload").inputValue();
  const root=`http://127.0.0.1:8001/workspaces/${wid}/datasets/${did}/uploads/${uid}`,runsRoot=`http://127.0.0.1:8001/workspaces/${wid}/datasets/${did}/decision-analysis`;
  const meaning=await(await page.request.get(`${root}/understanding`,{headers})).json();
  const response=await page.request.post(`${root}/understanding`,{headers,data:{revision_id:meaning.revision_id,expected_version:meaning.version,state:"confirmed",definition:{...meaning.definition,grain:"record",columns:meaning.definition.columns.map((c:{name:string})=>c.name==="id"?{...c,role:"identifier"}:c.name==="cohort"?{...c,role:"dimension"}:["a","b","amount"].includes(c.name)?{...c,role:"metric",unit:"units",currency:""}:c)}}});
  expect(response.status()).toBe(201);
  await page.getByRole("radio",{name:"Expert",exact:true}).check();
  await page.getByRole("navigation",{name:"Workspace navigation"}).getByRole("button",{name:"Anomalies & decisions",exact:true}).click();
  await page.getByRole("combobox",{name:"Analysis method",exact:true}).selectOption(method);
  const panel=page.getByRole("region",{name:method==="rolling"?"Calendar analysis":"Unusual combinations",exact:true});
  await panel.getByLabel("Analysis name",{exact:true}).fill(`Private ${method} example`);
  if(method==="rolling"){
    await panel.getByLabel("Coverage starts",{exact:true}).fill("2020-01-01");await panel.getByLabel("Coverage ends",{exact:true}).fill("2020-02-18");
    await panel.getByLabel("First period to evaluate",{exact:true}).fill("2020-01-21");
    await panel.getByRole("checkbox",{name:"I confirm these windows",exact:false}).check();
  }else{
    await panel.getByRole("checkbox",{name:"a · units",exact:true}).check();await panel.getByRole("checkbox",{name:"b · units",exact:true}).check();
    await panel.getByLabel("Reference group equals",{exact:true}).fill("reference");await panel.getByLabel("Comparison group equals",{exact:true}).fill("comparison");
    await panel.getByRole("checkbox",{name:"I chose this reference",exact:false}).check();
  }
  let posts=0;page.on("request",request=>{if(request.method()==="POST"&&request.url().endsWith(`/${method}-anomalies`))posts++;});
  const save=page.waitForResponse(r=>r.url().endsWith(`/${method}-anomalies`)&&r.request().method()==="POST");
  await panel.getByRole("button",{name:"Calculate and save privately",exact:true}).click();
  const created=await save;expect(created.status()).toBe(201);const saved=await created.json();
  const result=panel.getByRole("region",{name:method==="rolling"?"Saved calendar result":"Saved combination result",exact:true});await expect(result).toBeVisible();
  expect(saved.run.result.findings.length).toBeGreaterThan(0);
  await result.getByLabel(method==="rolling"?"Reason for your review":"Reason",{exact:true}).fill("Synthetic fixture: investigate before changing any source.");
  await result.getByRole("button",{name:"Save private review",exact:true}).click();await expect(panel).toContainText("Review saved.");
  await result.getByText("Download result",{exact:true}).click();await result.getByRole("combobox",{name:"File type",exact:true}).selectOption("xlsx");
  const downloadPromise=page.waitForEvent("download");await result.getByRole("button",{name:"Download Excel",exact:true}).click();
  const file=await downloadPromise;expect(readFileSync((await file.path())!).subarray(0,2).toString()).toBe("PK");
  for(const width of [1440,390,320]){await page.setViewportSize({width,height:1000});await page.emulateMedia({reducedMotion:"reduce"});await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await expect(result.locator('[data-chart-renderer="apache-echarts"]').first().locator("svg")).toBeVisible();}
  let denied=true;await page.route(runsRoot,route=>denied?route.fulfill({status:403,json:{error:{message:"Access revoked for this read"}}}):route.continue());
  await panel.getByRole("button",{name:"Reload saved results",exact:true}).click();await expect(panel.getByRole("alert")).toContainText("Access revoked");await expect(result).toHaveCount(0);await expect(panel.getByRole("button",{name:"Calculate and save privately",exact:true})).toHaveCount(0);
  denied=false;await panel.getByRole("button",{name:"Reload saved results",exact:true}).click();await panel.getByRole("button",{name:`Private ${method} example`,exact:true}).click();await expect(result).toBeVisible();expect(posts).toBe(1);
  const opened=await(await page.request.get(`${runsRoot}/${saved.run.id}`,{headers})).json();expect(opened.run).toEqual(saved.run);expect(opened.reviews).toHaveLength(1);
  expect((await(await page.request.get(`${root}/content`,{headers})).body()).toString()).toBe(csv);expect(errors).toEqual([]);
});
