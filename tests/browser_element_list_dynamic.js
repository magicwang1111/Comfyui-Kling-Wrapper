async (page, url = 'http://127.0.0.1:8199') => {
    await page.goto(url);
    await page.waitForFunction(() => window.LiteGraph?.registered_node_types['Comfyui-Kling-Wrapper Element List Builder']);
    await page.waitForLoadState('networkidle');
    await page.evaluate(async () => {
        const { app } = await import('/scripts/app.js');
        app.graph.clear();
        const node = LiteGraph.createNode('Comfyui-Kling-Wrapper Element List Builder');
        app.graph.add(node);
        window.elementBuilder = node;
        window.connectElement = (name) => {
            const source = LiteGraph.createNode('Comfyui-Kling-Wrapper Advanced Element Query');
            app.graph.add(source);
            const slot = window.elementBuilder.inputs.findIndex(i => i.name === name);
            if (slot < 0) throw new Error('Missing input ' + name);
            source.connect(0, window.elementBuilder, slot);
            return source;
        };
        const generation = LiteGraph.createNode('Comfyui-Kling-Wrapper Kling 4.0 OmniVideo');
        app.graph.add(generation);
        node.connect(0, generation, generation.inputs.findIndex(i => i.name === 'element_list'));
        const preview = LiteGraph.createNode('Comfyui-Kling-Wrapper Preview Video');
        app.graph.add(preview);
        generation.connect(0, preview, 0);
    });
    await page.waitForTimeout(150);
    await page.evaluate(() => {
        const inputs = window.elementBuilder.inputs.filter(i => i.name !== 'extra_element_ids');
        if (inputs.length !== 1 || inputs[0].name !== 'elements.element_1') throw new Error('Initial sockets incorrect: ' + inputs.map(i => i.name).join(', '));
    });
    for (let index = 1; index <= 7; index++) {
        await page.evaluate(index => window.connectElement('elements.element_' + index), index);
        await page.waitForTimeout(100);
    }
    await page.evaluate(async () => {
        const { app } = await import('/scripts/app.js');
        const node = window.elementBuilder;
        if (!node.inputs.some(i => i.name === 'elements.element_8' && i.link == null)) throw new Error('No next socket');
        const exported = (await app.graphToPrompt()).output[node.id].inputs;
        if (Object.keys(exported).filter(n => n.startsWith('elements.')).length !== 7) throw new Error('Missing dynamic exports');
        node.disconnectInput(node.inputs.findIndex(i => i.name === 'elements.element_2'));
    });
    await page.waitForTimeout(150);
    await page.evaluate(async () => {
        const { app } = await import('/scripts/app.js');
        const node = window.elementBuilder;
        const connected = node.inputs.filter(i => i.link != null);
        if (connected.length !== 6 || !connected.at(-1).label.includes('@element_6')) throw new Error('Disconnect numbering failed');
        await app.loadGraphData(app.graph.serialize());
        window.elementBuilder = app.graph._nodes.find(n => n.type.endsWith('Element List Builder'));
    });
    await page.waitForTimeout(150);
    await page.evaluate(async () => {
        const { app } = await import('/scripts/app.js');
        const node = window.elementBuilder;
        const exported = (await app.graphToPrompt()).output[node.id].inputs;
        if (Object.keys(exported).filter(n => n.startsWith('elements.')).length !== 6) throw new Error('Reload lost links');
        // Recreate the previous four-socket workflow, including a gap and manual IDs.
        const sourceType = node.inputs.find(i => i.name.startsWith('elements.')).type;
        for (let index = node.inputs.length - 1; index >= 0; index--) {
            if (node.inputs[index].name.startsWith('elements.')) node.removeInput(index);
        }
        for (let index = 1; index <= 4; index++) node.addInput('element_' + index, sourceType);
        window.connectElement('element_1');
        window.connectElement('element_3');
        node.widgets.find(w => w.name === 'extra_element_ids').value = 'manual-id';
        await app.loadGraphData(app.graph.serialize());
        window.elementBuilder = app.graph._nodes.find(n => n.type.endsWith('Element List Builder'));
    });
    await page.waitForTimeout(150);
    await page.evaluate(async () => {
        const { app } = await import('/scripts/app.js');
        const node = window.elementBuilder;
        const inputs = (await app.graphToPrompt()).output[node.id].inputs;
        if (!Array.isArray(inputs.element_1) || !Array.isArray(inputs.element_3) || inputs.extra_element_ids !== 'manual-id') throw new Error('Legacy workflow changed');
        if (!node.inputs.find(i => i.name === 'element_3').label.includes('@element_2')) throw new Error('Legacy gap order changed');
        window.connectElement('elements.element_1');
    });
    await page.waitForTimeout(150);
    await page.evaluate(async () => {
        const { app } = await import('/scripts/app.js');
        const node = window.elementBuilder;
        if (!node.inputs.find(i => i.name === 'elements.element_1').label.includes('@element_3')) throw new Error('New element was not appended');
        const inputs = (await app.graphToPrompt()).output[node.id].inputs;
        if (!Array.isArray(inputs['elements.element_1']) || !Array.isArray(inputs.element_3)) throw new Error('Mixed inputs not exported');
    });
    return { passed: true, dynamic: true, reload: true, legacy: true, appendToLegacy: true };
}
