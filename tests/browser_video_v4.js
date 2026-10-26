// Run against an isolated ComfyUI, never the user's active workflow:
// playwright-cli -s=kling4 run-code --filename tests/browser_video_v4.js
async (page) => {
    await page.goto("http://127.0.0.1:8199");
    await page.waitForFunction(() => window.LiteGraph?.registered_node_types["Comfyui-Kling-Wrapper Kling 4.0 OmniVideo"]);
    await page.waitForFunction(async () => {
        const { app } = await import("/scripts/app.js");
        return app.graph?._nodes.length > 0;
    });
    await page.waitForLoadState("networkidle");
    const result = await page.evaluate(async () => {
        const { app } = await import("/scripts/app.js");
        const check = (condition, message) => { if (!condition) throw new Error(message); };
        const prefix = "Comfyui-Kling-Wrapper Kling 4.0 ";
        app.graph.clear();
        const node = LiteGraph.createNode(prefix + "OmniVideo");
        app.graph.add(node);
        const prompt = node.widgets.find(w => w.name === "prompt");
        const panel = node.widgets.find(w => w.name === "kling4_reference_preview").element;
        const value = '参考@image_1的服装，@video_1的动作；@element_1用@voice_1说话。\n<img src=x onerror=alert(1)> @image_12 @image_1_invalid';
        prompt.value = value;
        prompt.callback?.(value);
        check(panel.querySelectorAll("span").length === 5, "Chinese-adjacent / numbered reference matching failed");
        check(!panel.querySelector("img"), "Prompt HTML must stay text");
        check(panel.children[2].textContent === value, "Preview changed prompt text");
        const serialized = node.serialize();
        check(serialized.widgets_values.length === 9, "Preview leaked into workflow serialization");
        check(serialized.widgets_values[0] === value, "Serialized prompt changed");
        const clone = node.clone();
        app.graph.add(clone);
        const clonePanel = clone.widgets.find(w => w.name === "kling4_reference_preview").element;
        check(clonePanel.children[2].textContent === value, "Clone failed to restore preview");
        app.graph.remove(clone);
        check(!clone.kling4ReferencePreview, "Node disposal did not clean up");
        const saved = app.graph.serialize();
        await app.loadGraphData(saved);
        const restored = app.graph._nodes.find(n => n.type === prefix + "OmniVideo");
        const restoredPrompt = restored.widgets.find(w => w.name === "prompt");
        const restoredPanel = restored.widgets.find(w => w.name === "kling4_reference_preview").element;
        check(restoredPrompt.value === value, "Workflow load changed prompt");
        check(restoredPanel.children[2].textContent === value, "Workflow load did not refresh preview");
        const image = LiteGraph.createNode(prefix + "Image2Video");
        app.graph.add(image);
        check(!!image.kling4ReferencePreview, "Image node missing preview");
        app.graph.remove(image);
        const text = LiteGraph.createNode(prefix + "Text2Video");
        check(!text.kling4ReferencePreview, "Text node must not offer unavailable materials");
        restored.pos = [80, 100];
        app.canvas.ds.scale = 0.75;
        app.canvas.ds.offset = [0, 0];
        window.kling4TestNode = restored;
        return { passed: 11, serializedWidgets: serialized.widgets_values.length, preview: "native textarea + colored preview" };
    });
    const button = await page.evaluate(() => {
        const node = window.kling4TestNode;
        const prompt = node.widgets.find(w => w.name === "prompt");
        prompt.value = "参考：";
        prompt.callback?.(prompt.value);
        const input = prompt.element;
        input.focus();
        input.setSelectionRange(input.value.length, input.value.length);
        const box = node.widgets.find(w => w.name === "kling4_reference_preview")
            .element.querySelector("button").getBoundingClientRect();
        return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
    });
    await page.mouse.click(button.x, button.y);
    await page.evaluate(() => {
        const node = window.kling4TestNode;
        const prompt = node.widgets.find(w => w.name === "prompt");
        if (prompt.value !== "参考：@image_1 ") throw new Error("Click insertion failed: " + prompt.value);
    });
    await page.keyboard.press("Control+z");
    await page.evaluate(() => {
        const prompt = window.kling4TestNode.widgets.find(w => w.name === "prompt");
        if (prompt.value !== "参考：") throw new Error("Native undo failed: " + prompt.value);
    });
    await page.keyboard.insertText("@voice_1说话");
    await page.evaluate(() => {
        const node = window.kling4TestNode;
        const panel = node.widgets.find(w => w.name === "kling4_reference_preview").element;
        if (panel.querySelector("span")?.textContent !== "@voice_1") throw new Error("Typing did not refresh preview");
    });
    return { ...result, passed: result.passed + 3, clickInsert: true, nativeUndo: true, liveTyping: true };
}
