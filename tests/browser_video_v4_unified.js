async(page, url = 'http://127.0.0.1:8199')=>{
 await page.goto(url);
 await page.waitForFunction(()=>window.LiteGraph?.registered_node_types['Comfyui-Kling-Wrapper Kling 4.0 OmniVideo']);
 await page.waitForLoadState('networkidle');
 await page.evaluate(async()=>{const {app}=await import('/scripts/app.js');app.graph.clear();
 const n=LiteGraph.createNode('Comfyui-Kling-Wrapper Kling 4.0 OmniVideo');app.graph.add(n);window.unifiedNode=n;n.pos=[600,100];
 const images=[];for(let i=0;i<4;i++){const src=LiteGraph.createNode('LoadImage');app.graph.add(src);src.widgets.find(w=>w.name==='image').value='example.jpg';images.push(src);}window.testImages=images;
 });
 await page.waitForTimeout(100);
 const initial=await page.evaluate(async()=>{const {app}=await import('/scripts/app.js');const n=window.unifiedNode;const fields=['first_frame','middle_frame.middle_frame_1','last_frame','image_1'];fields.forEach((f,i)=>window.testImages[i].connect(0,n,n.inputs.findIndex(s=>s.name===f)));return fields;});
 await page.waitForTimeout(150);
 await page.evaluate(()=>{const n=window.unifiedNode;['first_frame','middle_frame.middle_frame_1','last_frame','image_1'].forEach((f,i)=>{if(!n.inputs.find(s=>s.name===f).label.includes('@image_'+(i+1)))throw new Error('Wrong label '+f);});});
 await page.evaluate(async()=>{const {app}=await import('/scripts/app.js');const n=window.unifiedNode;const b=LiteGraph.createNode('ImageBatch');app.graph.add(b);window.testImages[1].connect(0,b,0);window.testImages[2].connect(0,b,1);b.connect(0,n,n.inputs.findIndex(s=>s.name==='middle_frame.middle_frame_1'));window.testBatch=b;});
 await page.waitForTimeout(150);
 await page.evaluate(()=>{const n=window.unifiedNode;if(!n.inputs.find(s=>s.name==='middle_frame.middle_frame_1').label.includes('@image_2、@image_3'))throw new Error('Batch numbering');if(!n.inputs.find(s=>s.name==='last_frame').label.includes('@image_4'))throw new Error('Tail after batch');if(!n.inputs.find(s=>s.name==='image_1').label.includes('@image_5'))throw new Error('Reference after batch');});
 await page.evaluate(async()=>{const {app}=await import('/scripts/app.js');const inner=LiteGraph.createNode('ImageBatch');app.graph.add(inner);window.testImages[0].connect(0,inner,0);window.testImages[3].connect(0,inner,1);inner.connect(0,window.testBatch,0);app.canvas.draw(true,true);});
 await page.waitForTimeout(150);
 const result=await page.evaluate(async()=>{const {app}=await import('/scripts/app.js');const n=window.unifiedNode;if(!n.inputs.find(s=>s.name==='image_1').label.includes('@image_6'))throw new Error('Upstream batch change left stale labels');const saved=app.graph.serialize();await app.loadGraphData(saved);return {passed:true,knownBatch:true,upstreamBatchChange:true};});
 await page.waitForTimeout(150);
 await page.evaluate(async()=>{const {app}=await import('/scripts/app.js');const n=app.graph._nodes.find(n=>n.type.includes('Kling 4.0'));const unknown=LiteGraph.createNode('EmptyImage');app.graph.add(unknown);unknown.connect(0,n,n.inputs.findIndex(s=>s.name==='middle_frame.middle_frame_1'));window.unifiedNode=n;});
 await page.waitForTimeout(150);
 await page.evaluate(()=>{const n=window.unifiedNode;const label=n.inputs.find(s=>s.name==='image_1').label;if(!label.includes('待执行确定')||label.includes('@image_'))throw new Error('Unknown batch must not guess '+label);});
 return {...result,unknownBatch:true};
}
