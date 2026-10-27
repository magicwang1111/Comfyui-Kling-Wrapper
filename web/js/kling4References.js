import { app } from "../../../scripts/app.js";

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
    title.textContent = "引用预览 · 彩色标记仅辅助阅读，实际提交原始提示词";
    title.style.color = "#aab8cb";
    const buttons = document.createElement("div");
    Object.assign(buttons.style, { display: "flex", flexWrap: "wrap", gap: "5px", margin: "6px 0" });
    const preview = document.createElement("div");
    Object.assign(preview.style, { whiteSpace: "pre-wrap", overflowWrap: "anywhere", userSelect: "text" });
    const help = document.createElement("div");
    help.style.color = "#aab8cb";
    help.style.fontSize = "11px";
    help.textContent = kind === "OmniVideo"
        ? "图片按参考图批次编号；视频按待编辑→特征 VIDEO→URL 列表编号；主体/音色按列表编号。点击标签插入，须连接对应素材。"
        : "首尾帧各一张，中间帧按批次编号。点击标签插入，须连接对应素材。";
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
        ? ["image_1", "video_1", "element_1", "voice_1", "first_frame", "middle_frame_1", "last_frame"]
        : ["first_frame", "middle_frame_1", "last_frame"];
    function setReferences(markers, description) {
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
            attachReferencePreview(this, kind);
            return result;
        };
        const configured = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            const result = configured?.apply(this, arguments);
            this.kling4ReferencePreview?.refresh();
            return result;
        };
        const removed = nodeType.prototype.onRemoved;
        nodeType.prototype.onRemoved = function () {
            this.kling4ReferencePreview?.dispose();
            return removed?.apply(this, arguments);
        };
    },
});
