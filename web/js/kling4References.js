import { app } from "../../../scripts/app.js";
import { updateImageReferences, IMAGE_ORDER_HELP, legacyImageWarning } from "./kling4ImageReferences.js";

const PREFIX = "Comfyui-Kling-Wrapper Kling 4.0 ";
const COLORS = {
    image: ["#93c5fd", "#172e4c"],
    video: ["#c4b5fd", "#342353"],
    element: ["#6ee7b7", "#143d31"],
    voice: ["#fcd34d", "#493714"],
    frame: ["#f9a8d4", "#47243b"],
};
const REFERENCES = /@(image_[1-9]\d*|video_[1-9]\d*|element_[1-9]\d*|voice_[1-9]\d*|first_frame|middle_frame_[1-9]\d*|last_frame)(?![A-Za-z0-9_])/g;

function colorToken(element, name) {
    const kind = name.includes("frame") ? "frame" : name.split("_")[0];
    const [color, background] = COLORS[kind];
    Object.assign(element.style, {
        color, background, border: `1px solid ${color}66`, borderRadius: "4px",
        padding: "0 3px", fontWeight: "700",
    });
}

export function renderReferences(container, text) {
    const fragment = document.createDocumentFragment();
    let cursor = 0;
    for (const match of text.matchAll(REFERENCES)) {
        fragment.append(document.createTextNode(text.slice(cursor, match.index)));
        const token = document.createElement("span");
        token.textContent = match[0];
        colorToken(token, match[1]);
        fragment.append(token);
        cursor = match.index + match[0].length;
    }
    fragment.append(document.createTextNode(text.slice(cursor)));
    container.replaceChildren(fragment);
}

export function attachReferencePreview(node, kind) {
    if (node.kling4ReferencePreview) return;
    const prompt = node.widgets?.find((widget) => widget.name === "prompt");
    if (!prompt) return;
    const root = document.createElement("div");
    root.className = "kling4-reference-preview";
    Object.assign(root.style, {
        boxSizing: "border-box", padding: "8px", background: "#1c2028", color: "#e5e7eb",
        border: "1px solid #475569", borderRadius: "6px", font: "12px/1.7 sans-serif",
        width: "100%", height: "100%", overflow: "auto",
    });
    const title = document.createElement("div");
    title.textContent = "引用预览 · 旧关键帧别名在提交时兼容转换为 image_N";
    title.style.color = "#aab8cb";
    const buttons = document.createElement("div");
    Object.assign(buttons.style, { display: "flex", flexWrap: "wrap", gap: "5px", margin: "6px 0" });
    const preview = document.createElement("div");
    Object.assign(preview.style, { whiteSpace: "pre-wrap", overflowWrap: "anywhere", userSelect: "text" });
    const help = document.createElement("div");
    help.style.color = "#aab8cb";
    help.style.fontSize = "11px";
    help.textContent = IMAGE_ORDER_HELP;
    root.append(title, buttons, preview, help);

    const refresh = () => renderReferences(preview, String(prompt.value ?? ""));
    const input = prompt.element instanceof HTMLTextAreaElement ? prompt.element : prompt.inputEl;
    const controller = new AbortController();
    if (input) {
        input.addEventListener("input", () => {
            renderReferences(preview, input.value);
        }, { signal: controller.signal });
    }
    const originalCallback = prompt.callback;
    const callback = function () {
        const result = originalCallback?.apply(this, arguments);
        refresh();
        return result;
    };
    prompt.callback = callback;

    const markers = kind === "OmniVideo"
        ? ["image_1", "video_1", "element_1", "voice_1"]
        : ["image_1"];
    function setReferences(markers, description) {
        const signature = JSON.stringify([markers, description]);
        if (root.dataset.referenceSignature === signature) return;
        root.dataset.referenceSignature = signature;
        buttons.replaceChildren();
        if (description) help.textContent = description;
        for (const marker of markers) {
            const button = document.createElement("button");
            button.type = "button";
            button.textContent = `@${marker}`;
            button.title = `在光标处插入 @${marker}，编号可自行修改`;
            colorToken(button, marker);
            button.style.cursor = "pointer";
            button.addEventListener("pointerdown", (event) => event.stopPropagation());
            button.addEventListener("mousedown", (event) => event.preventDefault());
            button.addEventListener("click", (event) => {
                event.stopPropagation();
                const token = `@${marker} `;
                if (input) {
                    input.focus();
                    // Native insertText preserves the textarea's undo stack where supported.
                    if (!document.execCommand("insertText", false, token)) {
                        input.setRangeText(token, input.selectionStart, input.selectionEnd, "end");
                        input.dispatchEvent(new Event("input", { bubbles: true }));
                    }
                    prompt.value = input.value;
                } else {
                    prompt.value = String(prompt.value ?? "") + token;
                }
                prompt.callback?.(prompt.value);
                node.setDirtyCanvas(true, true);
            });
            buttons.append(button);
        }
    }
    setReferences(markers);
    const widget = node.addDOMWidget("kling4_reference_preview", "kling4_preview", root, {
        serialize: false, hideOnZoom: false, getMinHeight: () => 155, getHeight: () => 180,
    });
    widget.serialize = false;
    node.widgets.splice(node.widgets.indexOf(widget), 1);
    node.widgets.splice(node.widgets.indexOf(prompt) + 1, 0, widget);
    node.kling4ReferencePreview = {
        refresh,
        setReferences,
        dispose() {
            controller.abort();
            if (prompt.callback === callback) prompt.callback = originalCallback;
            root.remove();
            delete node.kling4ReferencePreview;
        },
    };
    refresh();
    node.setSize([Math.max(node.size[0], 460), Math.max(node.size[1], node.computeSize()[1], kind === "OmniVideo" ? 800 : 600)]);
}

app.registerExtension({
    name: "ComfyuiKlingWrapper.Kling4References",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (![`${PREFIX}Image2Video`, `${PREFIX}OmniVideo`].includes(nodeData.name)) return;
        const kind = nodeData.name.slice(PREFIX.length);
        const created = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = created?.apply(this, arguments);
            this.properties.kling4UnifiedImageIds = 2;
            attachReferencePreview(this, kind);
            if (kind === "Image2Video") refreshImageLabels(this);
            return result;
        };
        const draw = nodeType.prototype.onDrawBackground;
        nodeType.prototype.onDrawBackground = function () {
            const result = draw?.apply(this, arguments);
            // Upstream ImageBatch changes do not change this node's own links.
            const images = updateImageReferences(this);
            const signature = JSON.stringify(images);
            if (signature !== this.kling4ImageSignature) {
                this.kling4ImageSignature = signature;
                if (kind === "Image2Video") refreshImageLabels(this);
                else this.kling4RefreshReferences?.();
            }
            return result;
        };
        const configured = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            const result = configured?.apply(this, arguments);
            this.properties.kling4UnifiedImageIds = arguments[0]?.properties?.kling4UnifiedImageIds || 1;
            this.kling4ReferencePreview?.refresh();
            if (kind === "Image2Video") refreshImageLabels(this);
            return result;
        };
        if (kind === "Image2Video") {
            const connections = nodeType.prototype.onConnectionsChange;
            nodeType.prototype.onConnectionsChange = function () {
                const result = connections?.apply(this, arguments);
                refreshImageLabels(this);
                return result;
            };
        }
        const removed = nodeType.prototype.onRemoved;
        nodeType.prototype.onRemoved = function () {
            this.kling4ReferencePreview?.dispose();
            return removed?.apply(this, arguments);
        };
    },
});

function refreshImageLabels(node) {
    const images = updateImageReferences(node);
    node.kling4ReferencePreview?.setReferences(images.markers.length ? images.markers : images.uncertain ? [] : ["image_1"],
        IMAGE_ORDER_HELP + (images.uncertain ? " 上游批次张数未知，后续编号执行时确定。" : "") + legacyImageWarning(node));
    node.graph?.setDirtyCanvas(true, true);
}
