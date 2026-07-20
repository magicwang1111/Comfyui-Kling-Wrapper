// Based on https://github.com/ArtVentureX/comfyui-animatediff/blob/main/web/js/vid_preview.js
import { app, ANIM_PREVIEW_WIDGET } from '../../../scripts/app.js';
import { createImageHost } from "../../../scripts/ui/imagePreview.js"

const MIN_PREVIEW_HEIGHT = 128;
const NODE_VERTICAL_PADDING = 52;

function makeVideoResponsive(videoElement) {
    videoElement.style.width = '100%';
    videoElement.style.height = '100%';
    videoElement.style.objectFit = 'contain';
    videoElement.style.display = 'block';
}

export function chainCallback(object, property, callback) {
    if (object == undefined) {
        //This should not happen.
        console.error("Tried to add callback to non-existant object");
        return;
    }
    if (property in object) {
        const callback_orig = object[property];
        object[property] = function () {
            const r = callback_orig.apply(this, arguments);
            callback.apply(this, arguments);
            return r;
        };
    } else {
        object[property] = callback;
    }
};

export function addVideoPreview(nodeType, options = {}) {
    const createVideoNode = (url) => {
        return new Promise((cb) => {
            const videoEl = document.createElement('video');
            videoEl.addEventListener('loadedmetadata', () => {
                videoEl.controls = false;
                videoEl.loop = true;
                videoEl.muted = true;
                makeVideoResponsive(videoEl);
                cb(videoEl);
            });
            videoEl.addEventListener('error', () => {
                cb();
            });
            videoEl.src = url;
        });
    };

    nodeType.prototype.onDrawBackground = function (ctx) {
        if (this.flags.collapsed) return;

        let imageURLs = this.images ?? [];
        let imagesChanged = false;

        if (JSON.stringify(this.displayingImages) !== JSON.stringify(imageURLs)) {
            this.displayingImages = imageURLs;
            imagesChanged = true;
        }

        if (!imagesChanged) {
            return;
        }

        if (!imageURLs.length) {
            this.imgs = null;
            this.animatedImages = false;
            return;
        }

        const promises = imageURLs.map((url) => {
            return createVideoNode(url);
        });

        Promise.all(promises)
            .then((imgs) => {
                this.imgs = imgs.filter(Boolean);
            })
            .then(() => {
                if (!this.imgs.length) return;

                this.animatedImages = true;
                const widgetIdx = this.widgets?.findIndex((w) => w.name === ANIM_PREVIEW_WIDGET);

                if (widgetIdx > -1) {
                    // Replace content
                    const widget = this.widgets[widgetIdx];
                    widget.options.host.updateImages(this.imgs);
                } else {
                    const host = createImageHost(this);
                    Object.assign(host.el.style, {
                        width: '100%',
                        height: '100%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        overflow: 'hidden',
                    });
                    const widget = this.addDOMWidget(ANIM_PREVIEW_WIDGET, 'img', host.el, {
                        host,
                        getMinHeight: () => MIN_PREVIEW_HEIGHT,
                        getMaxHeight: () => Math.max(
                            MIN_PREVIEW_HEIGHT,
                            this.size[1] - NODE_VERTICAL_PADDING,
                        ),
                        onDraw: host.onDraw,
                        hideOnZoom: false,
                    });
                    widget.serializeValue = () => ({
                        height: this.size[1],
                    });

                    widget.options.host.updateImages(this.imgs);
                }

                this.imgs.forEach((img) => {
                    if (img instanceof HTMLVideoElement) {
                        img.muted = true;
                        img.autoplay = true;
                        img.play();
                    }
                });

                // Force canvas update
                this.setDirtyCanvas(true, true);
            });
    };

    chainCallback(nodeType.prototype, "onExecuted", function (message) {
        if (message?.video_url) {
            this.images = message?.video_url;
            this.setDirtyCanvas(true);
        }
    });
}

app.registerExtension({
    name: "ComfyuiKlingWrapperVideoPreview",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "Comfyui-Kling-Wrapper Preview Video") {
            return;
        }
        addVideoPreview(nodeType);
    },
});
