import React, { useRef, useState } from "https://esm.sh/react@18.3.1";
import { ImagePlus, Send, X } from "https://esm.sh/lucide-react@0.468.0";
import { imageFileToPayload } from "../utils/image.js";

const h = React.createElement;

export default function MessageInput({ onSend, disabled }) {
  const fileRef = useRef(null);
  const [text, setText] = useState("");
  const [image, setImage] = useState(null);
  const [error, setError] = useState("");

  async function handleFile(event) {
    const file = event.target.files?.[0];
    setError("");
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setError("Please upload an image file.");
      return;
    }
    setImage(await imageFileToPayload(file));
  }

  function clearImage() {
    setImage(null);
    if (fileRef.current) fileRef.current.value = "";
  }

  function submit() {
    if (disabled || (!text.trim() && !image)) return;
    onSend({ text, image });
    setText("");
    clearImage();
  }

  return h(
    "footer",
    {
      className:
        "border-t border-zinc-200 bg-white/90 p-4 backdrop-blur dark:border-app-border dark:bg-app-bg/90"
    },
    h("div", { className: "mx-auto max-w-3xl" }, [
      image &&
        h(
          "div",
          {
            key: "preview",
            className:
              "mb-3 flex items-center gap-3 rounded-xl border border-zinc-200 bg-zinc-50 p-2 dark:border-app-border dark:bg-app-secondary"
          },
          [
            h("img", { key: "img", src: image.previewUrl, className: "h-14 w-14 rounded-lg object-cover", alt: image.name }),
            h("p", { key: "name", className: "flex-1 truncate text-sm" }, image.name),
            h("button", { key: "remove", onClick: clearImage, className: "rounded-lg p-2 hover:bg-white/10" }, h(X, { size: 16 }))
          ]
        ),
      error && h("p", { key: "error", className: "mb-2 text-sm text-red-500" }, error),
      h(
        "div",
        {
          key: "input",
          className:
            "flex items-end gap-2 rounded-2xl border border-zinc-200 bg-zinc-50 p-2 shadow-sm dark:border-app-border dark:bg-app-secondary"
        },
        [
          h(
            "button",
            {
              key: "upload",
              onClick: () => fileRef.current?.click(),
              disabled,
              className: "rounded-xl p-3 text-zinc-500 hover:bg-zinc-200 disabled:opacity-50 dark:hover:bg-white/10",
              "aria-label": "Upload image"
            },
            h(ImagePlus, { size: 20 })
          ),
          h("input", { key: "file", ref: fileRef, type: "file", accept: "image/*", hidden: true, onChange: handleFile }),
          h("textarea", {
            key: "textarea",
            value: text,
            onChange: (event) => setText(event.target.value),
            onKeyDown: (event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                submit();
              }
            },
            placeholder: "Ask anything...",
            rows: 1,
            disabled,
            className: "max-h-36 min-h-12 flex-1 resize-none bg-transparent px-2 py-3 text-sm outline-none"
          }),
          h(
            "button",
            {
              key: "send",
              onClick: submit,
              disabled: disabled || (!text.trim() && !image),
              className: "rounded-xl bg-accent-600 p-3 text-white transition hover:bg-accent-500 disabled:opacity-50",
              "aria-label": "Send"
            },
            h(Send, { size: 20 })
          )
        ]
      )
    ])
  );
}
