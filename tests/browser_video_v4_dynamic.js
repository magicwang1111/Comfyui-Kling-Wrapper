async (page)=>{
 await page.waitForFunction(()=>window.LiteGraph?.registered_node_types['Comfyui-Kling-Wrapper Kling 4.0 OmniVideo']);
 await page.waitForLoadState('networkidle');
 await page.evaluate(async()=>{
  const {app}=await import('/scripts/app.js');app.graph.clear();
  const n=LiteGraph.createNode('Comfyui-Kling-Wrapper Kling 4.0 OmniVideo');app.graph.add(n);window.dynamicNode=n;
 });
 await page.waitForTimeout(100);
 const initial=await page.evaluate(()=>window.dynamicNode.inputs.map(i=>i.name));
 if(initial.includes('reference_images')||initial.includes('image_2')||!initial.includes('image_1')||!initial.includes('feature_video_1'))throw new Error('Initial sockets wrong '+initial);
 await page.evaluate(async()=>{const {app}=await import('/scripts/app.js');const n=window.dynamicNode;const image=LiteGraph.createNode('LoadImage');app.graph.add(image);image.connect(0,n,n.inputs.findIndex(i=>i.name==='image_1'));window.firstImage=image;});
 await page.waitForTimeout(100);
 await page.evaluate(async()=>{const {app}=await import('/scripts/app.js');const n=window.dynamicNode;if(!n.inputs.some(i=>i.name==='image_2'))throw new Error('No next image');const image=LiteGraph.createNode('LoadImage');app.graph.add(image);image.connect(0,n,n.inputs.findIndex(i=>i.name==='image_2'));const video=LiteGraph.createNode('LoadVideo');app.graph.add(video);video.connect(0,n,n.inputs.findIndex(i=>i.name==='feature_video_1'));});
 await page.waitForTimeout(100);
 await page.evaluate(async()=>{const {app}=await import('/scripts/app.js');const n=window.dynamicNode;if(!n.inputs.some(i=>i.name==='feature_video_2'))throw new Error('No next video');n.disconnectInput(n.inputs.findIndex(i=>i.name==='image_1'));const base=n.widgets.find(w=>w.name==='base_video_url');base.value='https://example.com/base.mp4';base.callback?.(base.value);});
 await page.waitForTimeout(100);
 const result=await page.evaluate(async()=>{const {app}=await import('/scripts/app.js');const n=window.dynamicNode;const check=(c,m)=>{if(!c)throw new Error(m);};check(n.inputs.some(i=>i.name==='image_2'&&i.link!=null),'Renumbered image_2');check(n.inputs.find(i=>i.name==='feature_video_1').label.includes('@video_2'),'Base offset wrong');const preview=LiteGraph.createNode('Comfyui-Kling-Wrapper Preview Video');app.graph.add(preview);n.connect(0,preview,0);const saved=app.graph.serialize();await app.loadGraphData(saved);const exported=await app.graphToPrompt();const gen=Object.values(exported.output).find(x=>x.class_type.includes('Kling 4.0'));check(Array.isArray(gen.inputs.image_2),'Dynamic image not exported');check(Array.isArray(gen.inputs.feature_video_1),'Dynamic video not exported');check(!gen.inputs.image_1,'Disconnected image exported');window.dynamicNode=app.graph._nodes.find(x=>x.type.includes('Kling 4.0'));return {inputs:Object.keys(gen.inputs),passed:true};});
 await page.waitForTimeout(100);
 await page.evaluate(async()=>{
  const {app}=await import('/scripts/app.js');const n=window.dynamicNode;
  const w=n.widgets.find(w=>w.name==='base_video_url');w.value='';w.callback?.('');
  n.addInput('base_video_url','STRING',{widget:{name:'base_video_url'}});
  const source=LiteGraph.createNode('Comfyui-Kling-Wrapper Custom Voice Query');app.graph.add(source);
  source.connect(0,n,n.inputs.findIndex(i=>i.name==='base_video_url'));
 });
 await page.waitForTimeout(100);
 await page.evaluate(async()=>{const {app}=await import('/scripts/app.js');const n=window.dynamicNode;if(!n.inputs.find(i=>i.name==='feature_video_1').label.includes('@video_2'))throw new Error('Connected base URL offset wrong');const wf=app.graph.serialize();await app.loadGraphData(wf);});
 await page.waitForTimeout(100);
 await page.evaluate(async()=>{const {app}=await import('/scripts/app.js');const n=app.graph._nodes.find(n=>n.type.includes('Kling 4.0'));if(!n.inputs.find(i=>i.name==='feature_video_1').label.includes('@video_2'))throw new Error('Connected base URL offset lost on reload');});
 return {...result,connectedBaseUrl:true};
}
