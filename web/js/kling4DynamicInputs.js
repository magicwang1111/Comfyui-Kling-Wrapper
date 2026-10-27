import { app } from "../../../scripts/app.js";

const NODE = "Comfyui-Kling-Wrapper Kling 4.0 OmniVideo";

export function stabilizeInputs(node) {
    if (node.kling4Stabilizing) return;
    node.kling4Stabilizing = true;
    try {
        const linked = (name) => node.inputs?.some(i => i.name === name && i.link != null);
        const base = linked("base_video") || linked("base_video_url") || !!String(node.widgets?.find(w => w.name === "base_video_url")?.value || "").trim();
        const legacyVideo = linked("feature_video");
        for (const name of ["reference_images", "feature_video"]) {
            const index = node.inputs?.findIndex(i => i.name === name && i.link == null);
            if (index >= 0) node.removeInput(index);
        }
        for (const [prefix, type, limit] of [["image", "IMAGE", 10], ["feature_video", "VIDEO", 5 - Number(base) - Number(legacyVideo)]]) {
            const pattern = new RegExp(`^${prefix}_(\\d+)$`);
            const matches = () => node.inputs.filter(i => pattern.test(i.name));
            const connected = matches().filter(i => i.link != null);
            const used = new Set(connected.map(i => Number(i.name.match(pattern)[1])));
            const legacyImages = prefix === "image" && linked("reference_images");
            let available = 1;
            while (used.has(available)) available++;
            const wanted = !legacyImages && connected.length < limit && available <= (prefix === "image" ? 10 : 5)
                ? `${prefix}_${available}` : null;
            for (let index = node.inputs.length - 1; index >= 0; index--) {
                const input = node.inputs[index];
                if (pattern.test(input.name) && input.link == null && input.name !== wanted) node.removeInput(index);
            }
            if (wanted && !node.inputs.some(i => i.name === wanted)) node.addInput(wanted, type);
            for (const input of matches()) {
                const index = Number(input.name.match(pattern)[1]);
                const marker = prefix === "image" ? `image_${index}` : `video_${index + Number(base) + Number(legacyVideo)}`;
                input.label = `${input.name} → @${marker}`;
                input.kling4Reference = marker;
            }
        }
        const baseInput = node.inputs.find(i => i.name === "base_video");
        if (baseInput) baseInput.label = "base_video → @video_1（接入时占用）";
        const legacy = node.inputs.find(i => i.name === "feature_video");
        if (legacy) legacy.label = `feature_video → @video_${base ? 2 : 1}（旧输入）`;
        const markers = node.inputs.filter(i => i.kling4Reference).map(i => i.kling4Reference);
        if (base || legacyVideo) markers.push("video_1");
        if (base && legacyVideo) markers.push("video_2");
        node.kling4ReferencePreview?.setReferences([...new Set([...markers, "element_1", "voice_1", "first_frame", "middle_frame_1", "last_frame"])],
            `${base ? "base_video = @video_1；特征视频引用号已后移。" : "未提供 base_video；特征视频从 @video_1 开始。"} 增删 base_video 会改变视频引用号，请检查提示词。总素材≤15（含关键帧、主体和音色），执行前按实际数量校验。`);
    } finally {
        node.kling4Stabilizing = false;
    }
    node.graph?.setDirtyCanvas(true, true);
}

function schedule(node) {
    clearTimeout(node.kling4DynamicTimer);
    node.kling4DynamicTimer = setTimeout(() => {
        node.kling4DynamicTimer = null;
        stabilizeInputs(node);
    }, 32);
}

app.registerExtension({
    name: "ComfyuiKlingWrapper.Kling4DynamicInputs",
    beforeRegisterNodeDef(nodeType, data) {
        if (data.name !== NODE) return;
        for (const event of ["onNodeCreated", "onConfigure", "onConnectionsChange"]) {
            const original = nodeType.prototype[event];
            nodeType.prototype[event] = function () {
                const result = original?.apply(this, arguments);
                schedule(this);
                if (event === "onNodeCreated") {
                    const widget = this.widgets?.find(w => w.name === "base_video_url");
                    if (widget) {
                        const callback = widget.callback;
                        widget.callback = (...args) => { const result = callback?.apply(widget, args); schedule(this); return result; };
                    }
                }
                return result;
            };
        }
        const removed = nodeType.prototype.onRemoved;
        nodeType.prototype.onRemoved = function () {
            clearTimeout(this.kling4DynamicTimer);
            return removed?.apply(this, arguments);
        };
    },
});
