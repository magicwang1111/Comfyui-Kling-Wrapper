import { app } from "../../../scripts/app.js";

function refresh(node) {
    // Keep connected legacy sockets so saved workflows and API prompts retain their names.
    for (let index = node.inputs.length - 1; index >= 0; index--) {
        const input = node.inputs[index];
        if (/^element_[1-4]$/.test(input.name) && input.link == null) node.removeInput(index);
    }
    const elements = node.inputs.filter(i => /^(elements\.)?element_\d+$/.test(i.name))
        .sort((a, b) => Number(a.name.startsWith("elements.")) - Number(b.name.startsWith("elements."))
            || Number(a.name.split("_").at(-1)) - Number(b.name.split("_").at(-1)));
    let count = 0;
    for (const input of elements) {
        input.label = input.link == null ? "连接下一个主体" : `主体 ${++count} → @element_${count}`;
    }
    node.graph?.setDirtyCanvas(true, true);
}

app.registerExtension({
    name: "ComfyuiKlingWrapper.ElementListDynamicInputs",
    beforeRegisterNodeDef(nodeType, data) {
        if (data.name !== "Comfyui-Kling-Wrapper Element List Builder") return;
        for (const event of ["onNodeCreated", "onConfigure", "onConnectionsChange"]) {
            const original = nodeType.prototype[event];
            nodeType.prototype[event] = function () {
                const result = original?.apply(this, arguments);
                clearTimeout(this.klingElementTimer);
                this.klingElementTimer = setTimeout(() => refresh(this), 32);
                return result;
            };
        }
        const removed = nodeType.prototype.onRemoved;
        nodeType.prototype.onRemoved = function () {
            clearTimeout(this.klingElementTimer);
            return removed?.apply(this, arguments);
        };
    },
});
