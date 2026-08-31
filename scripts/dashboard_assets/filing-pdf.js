/* Local, canvas-only rendering of immutable filing bytes. No PDF viewer scripting. */
(() => {
  "use strict";
  const VERSION = "6.3.289";
  const scriptUrl = document.currentScript?.src || new URL("assets/filing-pdf.js", document.baseURI).href;
  const assetBase = new URL("vendor/pdfjs/", scriptUrl);
  const moduleUrl = new URL(`pdf.mjs?v=${VERSION}`, assetBase);
  const workerUrl = new URL(`pdf.worker.mjs?v=${VERSION}`, assetBase);
  const MAX_BYTES = 32 * 1024 * 1024;
  const MAX_CANVASES = 4;
  const MAX_PIXELS = 4 * 1024 * 1024;
  let modulePromise;
  const owners = new WeakMap();

  function aborted() { return new DOMException("Filing viewer closed.", "AbortError"); }
  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }
  function loadModule() {
    if (assetBase.origin !== location.origin || !/^https?:$/.test(assetBase.protocol)) {
      return Promise.reject(new Error("The local PDF renderer must be served from PolitiTrack's own origin."));
    }
    if (!modulePromise) modulePromise = import(moduleUrl.href).catch(error => { modulePromise = null; throw error; });
    return modulePromise;
  }

  async function render(bytes, container, options = {}) {
    if (!(bytes instanceof Uint8Array) || !bytes.byteLength || bytes.byteLength > MAX_BYTES) {
      throw new Error("This PDF is empty or exceeds the in-app viewer's 32 MiB limit. Download the original filing to inspect it.");
    }
    if (!container || typeof container.replaceChildren !== "function") throw new Error("The filing viewer container is unavailable.");
    owners.get(container)?.destroy();
    const signal = options.signal;
    if (signal?.aborted) throw aborted();
    const maxPages = Math.max(1, Math.min(300, Number.isInteger(options.maxPages) ? options.maxPages : 300));
    const frame = node("div", "pt-pdf");
    const notice = node("p", "pt-pdf-status", "Loading the cached filing with the local PDF renderer…");
    notice.setAttribute("role", "status");
    frame.append(notice);
    container.replaceChildren(frame);
    container.setAttribute("aria-busy", "true");
    let closed = false, pdf, loadingTask, workerPort, pdfWorker, observer, resizeObserver;
    let running = false, resizeTimer = 0, lastWidth = 0, started = false;
    const slots = [];
    const handle = {destroy, pageCount: 0};
    owners.set(container, handle);

    function destroy() {
      if (closed) return;
      closed = true;
      clearTimeout(resizeTimer);
      observer?.disconnect();
      resizeObserver?.disconnect();
      window.removeEventListener("resize", scheduleResize);
      signal?.removeEventListener("abort", destroy);
      for (const slot of slots) release(slot);
      if (loadingTask) Promise.resolve(loadingTask.destroy()).catch(() => {});
      if (pdfWorker) Promise.resolve(pdfWorker.destroy()).catch(() => {});
      workerPort?.terminate();
      if (owners.get(container) === handle) {
        owners.delete(container);
        container.removeAttribute("aria-busy");
        container.replaceChildren();
      }
    }
    signal?.addEventListener("abort", destroy, {once: true});
    function alive() { if (closed || signal?.aborted) throw aborted(); }
    function waitFor(promise) {
      return new Promise((resolve, reject) => {
        const onAbort = () => finish(reject, aborted());
        const timer = setTimeout(() => {
          const error = new Error("The PDF renderer exceeded its 30-second operation limit. Download the original filing to inspect it.");
          error.name = "TimeoutError";
          finish(reject, error);
        }, 30000);
        function finish(callback, value) {
          clearTimeout(timer);
          signal?.removeEventListener("abort", onAbort);
          callback(value);
        }
        signal?.addEventListener("abort", onAbort, {once: true});
        if (closed || signal?.aborted) { onAbort(); return; }
        Promise.resolve(promise).then(value => finish(resolve, value), error => finish(reject, error));
      });
    }
    function width() { return Math.max(1, Math.floor(frame.clientWidth || container.clientWidth || 320)); }
    function release(slot) {
      slot.generation += 1;
      slot.renderTask?.cancel();
      slot.renderTask = null;
      if (slot.canvas) { slot.canvas.width = slot.canvas.height = 0; slot.canvas.remove(); slot.canvas = null; }
      slot.loadedWidth = 0;
      slot.textLoaded = false;
      slot.text.textContent = "";
      slot.details.open = false;
      if (!closed) slot.placeholder.hidden = false;
    }
    function limitMemory(candidate) {
      const allocated = slots.filter(slot => slot !== candidate && slot.canvas);
      while (allocated.length >= MAX_CANVASES) {
        const victim = allocated.sort((a, b) => Number(a.wanted) - Number(b.wanted) || Math.abs(b.number - candidate.number) - Math.abs(a.number - candidate.number)).shift();
        release(victim);
      }
    }
    function pageError(slot, error) {
      if (closed || error?.name === "RenderingCancelledException" || error?.name === "AbortError") return;
      if (started && error?.name === "TimeoutError") {
        destroy();
        const failure = node("p", "pt-pdf-error", error.message);
        failure.setAttribute("role", "alert");
        container.replaceChildren(failure);
        return;
      }
      slot.failed = true;
      slot.placeholder.hidden = false;
      slot.placeholder.textContent = `Page ${slot.number} could not be rendered. Download the original filing to inspect this page.`;
      slot.placeholder.setAttribute("role", "alert");
      if (slot.canvas) { slot.canvas.width = slot.canvas.height = 0; slot.canvas.remove(); slot.canvas = null; }
    }
    async function draw(slot) {
      alive();
      const generation = slot.generation;
      let page;
      try {
        page = await waitFor(pdf.getPage(slot.number));
        alive();
        if (generation !== slot.generation) return;
        const intrinsic = page.getViewport({scale: 1});
        if (![intrinsic.width, intrinsic.height].every(value => Number.isFinite(value) && value > 0)
            || intrinsic.height / intrinsic.width > 20 || intrinsic.width / intrinsic.height > 20) {
          throw new Error("The page dimensions exceed this viewer's limits.");
        }
        const cssWidth = width();
        const viewport = page.getViewport({scale: cssWidth / intrinsic.width});
        const density = Math.min(window.devicePixelRatio || 1, 2,
          8192 / viewport.width, 8192 / viewport.height,
          Math.sqrt(MAX_PIXELS / (viewport.width * viewport.height)));
        limitMemory(slot);
        const canvas = node("canvas", "pt-pdf-canvas");
        canvas.width = Math.max(1, Math.floor(viewport.width * density));
        canvas.height = Math.max(1, Math.floor(viewport.height * density));
        canvas.style.width = "100%";
        canvas.style.height = "auto";
        canvas.setAttribute("role", "img");
        canvas.setAttribute("aria-label", `Official filing, page ${slot.number} of ${pdf.numPages}. Extracted text is available below the page when present.`);
        slot.sheet.style.aspectRatio = `${viewport.width} / ${viewport.height}`;
        slot.sheet.style.minHeight = "0";
        slot.canvas = canvas;
        slot.sheet.append(canvas);
        const context = canvas.getContext("2d", {alpha: false});
        if (!context) throw new Error("Canvas rendering is unavailable in this browser.");
        slot.renderTask = page.render({canvas, viewport,
          transform: density === 1 ? null : [density, 0, 0, density, 0, 0],
          annotationMode: 1, background: "rgb(255,255,255)"});
        await waitFor(slot.renderTask.promise);
        alive();
        if (generation !== slot.generation) return;
        slot.renderTask = null;
        slot.loadedWidth = cssWidth;
        slot.placeholder.hidden = true;
      } catch (error) {
        pageError(slot, error);
        if (!started || error?.name === "AbortError") throw error;
      } finally {
        // Release PDF operator/image data; retained canvases hold only pixels.
        try { page?.cleanup(); } catch { /* A cancelled task may still be settling. */ }
      }
    }
    async function pump() {
      if (running || closed || !started) return;
      running = true;
      const attempted = new Set();
      try {
        while (!closed) {
          const candidates = slots.filter(slot => slot.wanted && !slot.failed && !attempted.has(slot) && (!slot.canvas || slot.loadedWidth !== width()));
          if (!candidates.length) break;
          const center = window.innerHeight / 2;
          candidates.sort((a, b) => Math.abs(a.sheet.getBoundingClientRect().top - center) - Math.abs(b.sheet.getBoundingClientRect().top - center));
          const slot = candidates[0];
          attempted.add(slot);
          if (slot.canvas) release(slot);
          await draw(slot);
        }
      } catch (error) { if (!closed && error?.name !== "AbortError") notice.textContent = "Some pages could not be displayed. Download the original filing to inspect all evidence."; }
      finally { running = false; }
    }
    function scheduleResize() {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        if (closed || Math.abs(width() - lastWidth) < 2) return;
        lastWidth = width();
        for (const slot of slots) if (slot.canvas && !slot.renderTask) release(slot);
        void pump();
      }, 180);
    }
    async function textFor(slot) {
      if (closed || !slot.details.open || slot.textLoaded) return;
      slot.textLoaded = true;
      const generation = slot.generation;
      slot.text.textContent = "Reading text from this cached page…";
      try {
        const page = await waitFor(pdf.getPage(slot.number));
        alive();
        const content = await waitFor(page.getTextContent());
        alive();
        if (generation !== slot.generation || !slot.details.open) return;
        // Never interpret extracted filing strings as markup or activate links.
        const text = content.items.map(item => typeof item.str === "string" ? item.str + (item.hasEOL ? "\n" : " ") : "").join("");
        slot.text.textContent = text.trim() ? text.slice(0, 200000) + (text.length > 200000 ? "\n[Text preview limit reached. Download the original filing.]" : "") : "No extractable text is present on this page. The image above is the original filing page.";
      } catch (error) {
        if (error?.name === "TimeoutError") pageError(slot, error);
        else if (!closed) slot.text.textContent = "Text could not be extracted. Use the original filing page or Download.";
      }
    }
    try {
      const library = await waitFor(loadModule());
      alive();
      if (library.version !== VERSION) throw new Error("The local PDF renderer and its worker have mismatched versions. Reload PolitiTrack.");
      if (typeof Worker !== "function") throw new Error("This browser cannot start the local PDF worker. Download the original filing to inspect it.");
      // Supplying an explicit same-origin Worker prevents a blob/CDN worker or
      // a silent main-thread fallback. No PDF-provided URL is ever passed in.
      workerPort = new Worker(workerUrl.href, {type: "module", name: "polititrack-filing-pdf"});
      pdfWorker = new library.PDFWorker({port: workerPort});
      loadingTask = library.getDocument({data: bytes.slice(), worker: pdfWorker,
        cMapUrl: new URL("cmaps/", assetBase).href, cMapPacked: true,
        standardFontDataUrl: new URL("standard_fonts/", assetBase).href,
        wasmUrl: new URL("wasm/", assetBase).href, iccUrl: new URL("iccs/", assetBase).href,
        useWorkerFetch: true, useWasm: true, enableXfa: false, isEvalSupported: false,
        disableAutoFetch: true, disableRange: true, disableStream: true,
        stopAtErrors: true, maxImageSize: 16 * 1024 * 1024,
        canvasMaxAreaInBytes: 16 * 1024 * 1024, isImageDecoderSupported: false,
        verbosity: 0});
      loadingTask.onPassword = () => {
        notice.textContent = "This filing is password-protected. Download the original document and use an authorized PDF reader.";
        void loadingTask.destroy();
      };
      pdf = await waitFor(loadingTask.promise);
      alive();
      if (pdf.numPages > maxPages) throw new Error(`This filing has ${pdf.numPages} pages, above the in-app viewer's ${maxPages}-page limit. Download the original filing to inspect every page.`);
      if (!Number.isInteger(pdf.numPages) || pdf.numPages < 1) throw new Error("This filing contains no readable pages.");
      handle.pageCount = pdf.numPages;
      notice.textContent = `${pdf.numPages} ${pdf.numPages === 1 ? "page" : "pages"} · Original cached filing · Pages render as you scroll. Use browser zoom to inspect details.`;
      for (let number = 1; number <= pdf.numPages; number += 1) {
        const section = node("section", "pt-pdf-page");
        section.setAttribute("aria-label", `Page ${number}`);
        const heading = node("h3", "pt-pdf-page-title", `Page ${number} of ${pdf.numPages}`);
        const sheet = node("div", "pt-pdf-sheet");
        const placeholder = node("p", "pt-pdf-placeholder", `Page ${number} loads when you scroll to it.`);
        const details = node("details", "pt-pdf-text");
        details.append(node("summary", "", `Read extracted text for page ${number}`));
        const text = node("p", "pt-pdf-extracted"); details.append(text);
        sheet.append(placeholder); section.append(heading, sheet, details); frame.append(section);
        const slot = {number, section, sheet, placeholder, details, text, generation: 0,
          canvas: null, renderTask: null, loadedWidth: 0, wanted: number === 1, failed: false, textLoaded: false};
        details.addEventListener("toggle", () => { void textFor(slot); });
        slots.push(slot);
      }
      await draw(slots[0]);
      alive();
      started = true;
      lastWidth = width();
      container.removeAttribute("aria-busy");
      if (typeof IntersectionObserver === "function") {
        observer = new IntersectionObserver(entries => {
          for (const entry of entries) {
            const slot = slots.find(item => item.section === entry.target);
            if (!slot) continue;
            slot.wanted = entry.isIntersecting;
            if (!entry.isIntersecting) release(slot);
          }
          void pump();
        }, {rootMargin: "400px 0px"});
        for (const slot of slots) observer.observe(slot.section);
      } else {
        // Older environments still offer an explicit working control per page.
        for (const slot of slots.slice(1)) {
          const button = node("button", "button", `Load page ${slot.number}`);
          button.type = "button";
          button.addEventListener("click", () => { slot.wanted = true; void pump(); });
          slot.placeholder.replaceChildren(button);
        }
      }
      if (typeof ResizeObserver === "function") { resizeObserver = new ResizeObserver(scheduleResize); resizeObserver.observe(container); }
      else window.addEventListener("resize", scheduleResize);
      return handle;
    } catch (error) {
      const wasClosed = closed;
      destroy();
      if (wasClosed || signal?.aborted) throw aborted();
      const message = error?.message && !/password/i.test(error.message) ? error.message : "This PDF could not be rendered here. Download the original filing to inspect it.";
      const failure = node("p", "pt-pdf-error", message);
      failure.setAttribute("role", "alert");
      container.replaceChildren(failure);
      throw new Error(message);
    }
  }
  window.PTFilingPdf = Object.freeze({render, version: VERSION});
})();
