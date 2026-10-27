function loadedImageCount(node) {
    const value = String(node.widgets?.find(w => w.name === "image")?.value || "");
    if (/\.(jpe?g|bmp)(?: \[(?:input|output|temp)\])?$/i.test(value)) return 1;
    if (node.kling4ImageCount?.value === value) return node.kling4ImageCount.count;
    const state = { value, count: null };
    node.kling4ImageCount = state;
    if (!value || typeof ImageDecoder === "undefined") return null;
    const annotated = value.match(/ \[(input|output|temp)\]$/);
    const filename = value.replace(/ \[(input|output|temp)\]$/, "").replaceAll("\\", "/");
    const slash = filename.lastIndexOf("/");
    const params = new URLSearchParams({ filename: filename.slice(slash + 1), subfolder: filename.slice(0, Math.max(slash, 0)), type: annotated?.[1] || "input" });
    const extension = filename.split(".").pop().toLowerCase();
    const type = { png: "image/png", apng: "image/png", webp: "image/webp", gif: "image/gif" }[extension];
    if (!type) return null;
    (async () => {
        let decoder;
        try {
            if (!await ImageDecoder.isTypeSupported(type)) return;
            const response = await fetch(`/view?${params}`);
            if (!response.ok) return;
            decoder = new ImageDecoder({ data: await response.arrayBuffer(), type });
            await decoder.tracks.ready;
            await decoder.completed;
            const count = decoder.tracks.selectedTrack?.frameCount;
            if (Number.isInteger(count) && count > 0) state.count = count;
        } catch {
            // Unknown or unreadable batches stay explicitly unnumbered.
        } finally {
            decoder?.close();
            node.graph?.setDirtyCanvas(true, true);
        }
    })();
    return null;
}

function batchSize(node, slot, seen = new Set()) {
    const upstream = node.getInputNode(slot);
    if (!upstream || seen.has(upstream.id)) return null;
    const next = new Set(seen).add(upstream.id);
    if (upstream.type === "LoadImage") return loadedImageCount(upstream);
    if (upstream.type === "ImageBatch") {
        const sizes = upstream.inputs.map((input, i) => batchSize(upstream, i, next));
        return sizes.every(n => n != null) ? sizes.reduce((a, b) => a + b, 0) : null;
    }
    if (upstream.type === "Reroute") return batchSize(upstream, 0, next);
    return null;
}

export function updateImageReferences(node) {
    const names = ["first_frame", "middle_frames", "last_frame"];
    names.push(...node.inputs.filter(i => /^image_\d+$/.test(i.name))
        .sort((a, b) => Number(a.name.split("_")[1]) - Number(b.name.split("_")[1])).map(i => i.name));
    names.push("reference_images");
    let next = 1;
    const markers = [];
    let uncertain = false;
    for (const name of names) {
        const slot = node.inputs.findIndex(i => i.name === name);
        if (slot < 0) continue;
        const input = node.inputs[slot];
        delete input.kling4Reference;
        if (input.link == null) {
            input.label = `${name}（未连接）`;
            continue;
        }
        const count = ["middle_frames", "reference_images"].includes(name) ? batchSize(node, slot) : 1;
        if (count == null) uncertain = true;
        if (uncertain) {
            input.label = `${name} → image_N（批次数量待执行确定）`;
            continue;
        }
        const refs = Array.from({ length: count }, (_, index) => `image_${next + index}`);
        input.label = `${name} → ${refs.map(id => `@${id}`).join("、")}`;
        input.kling4Reference = refs[0];
        markers.push(...refs);
        next += count;
    }
    return { markers, uncertain };
}

export const IMAGE_ORDER_HELP = "图片统一按首帧→中间帧→尾帧→参考图编号，增删前面的图片会改变后续 image_N，请检查提示词。";

export function legacyImageWarning(node) {
    return node.properties?.kling4UnifiedImageIds === 1
        ? " 旧 workflow 提示：图片已改为统一编号，请核对原 @image_N 的指向；旧关键帧别名仍会兼容转换。" : "";
}
