async (page, url = 'http://127.0.0.1:8199') => {
    await page.goto(url);
    await page.waitForFunction(() => window.LiteGraph?.registered_node_types['Comfyui-Kling-Wrapper Kling 4.0 OmniVideo']);
    await page.waitForLoadState('networkidle');
    for (const kind of ['Image2Video', 'OmniVideo']) {
        await page.evaluate(async (kind) => {
            const { app } = await import('/scripts/app.js');
            app.graph.clear();
            const node = LiteGraph.createNode('Comfyui-Kling-Wrapper Kling 4.0 ' + kind);
            app.graph.add(node);
            window.middleTest = node;
            window.connectMiddleTest = (name) => {
                const source = LiteGraph.createNode('LoadImage');
                app.graph.add(source);
                source.widgets.find(w => w.name === 'image').value = 'example.jpg';
                const slot = window.middleTest.inputs.findIndex(i => i.name === name);
                if (slot < 0) throw new Error('Missing input: ' + name);
                source.connect(0, window.middleTest, slot);
            };
        }, kind);
        await page.waitForTimeout(200);
        await page.evaluate(() => {
            if (window.middleTest.inputs.some(i => i.name === 'middle_frames')) throw new Error('Legacy socket visible on new node');
            window.connectMiddleTest('first_frame');
            window.connectMiddleTest('middle_frame.middle_frame_1');
        });
        await page.waitForTimeout(200);
        await page.evaluate((kind) => {
            window.connectMiddleTest('middle_frame.middle_frame_2');
            window.connectMiddleTest('last_frame');
            if (kind === 'OmniVideo') window.connectMiddleTest('image_1');
        }, kind);
        await page.waitForTimeout(200);
        await page.evaluate(async (kind) => {
            const { app } = await import('/scripts/app.js');
            const node = window.middleTest;
            const names = ['first_frame', 'middle_frame.middle_frame_1', 'middle_frame.middle_frame_2', 'last_frame'];
            if (kind === 'OmniVideo') names.push('image_1');
            names.forEach((name, index) => {
                const label = node.inputs.find(i => i.name === name)?.label;
                if (!label?.includes('@image_' + (index + 1))) throw new Error('Incorrect label: ' + label);
            });
            if (!node.inputs.some(i => i.name === 'middle_frame.middle_frame_3')) throw new Error('Next middle frame missing');
            const preview = LiteGraph.createNode('Comfyui-Kling-Wrapper Preview Video');
            app.graph.add(preview);
            node.connect(0, preview, 0);
            await app.loadGraphData(app.graph.serialize());
            window.middleTest = app.graph._nodes.find(n => n.type.endsWith(kind));
        }, kind);
        await page.waitForTimeout(200);
        await page.evaluate(async () => {
            const { app } = await import('/scripts/app.js');
            const exported = await app.graphToPrompt();
            const inputs = exported.output[window.middleTest.id].inputs;
            for (const name of ['middle_frame.middle_frame_1', 'middle_frame.middle_frame_2']) {
                if (!Array.isArray(inputs[name])) throw new Error('Missing exported link: ' + name);
            }
            if (inputs['middle_frame.middle_frame_3']) throw new Error('Empty middle frame exported');
            window.middleTest.disconnectInput(window.middleTest.inputs.findIndex(i => i.name === 'middle_frame.middle_frame_1'));
        });
        await page.waitForTimeout(200);
        await page.evaluate(async () => {
            const { app } = await import('/scripts/app.js');
            const node = window.middleTest;
            if (!node.inputs.find(i => i.name === 'last_frame').label.includes('@image_3')) throw new Error('Tail label stale after disconnect');
            const exported = await app.graphToPrompt();
            const mids = Object.keys(exported.output[node.id].inputs).filter(n => n.startsWith('middle_frame.'));
            if (mids.length !== 1) throw new Error('Disconnected middle frame exported');
        });
    }
    return { passed: true, nodes: ['Image2Video', 'OmniVideo'], growth: true, numbering: true, reload: true, export: true, disconnect: true };
}
