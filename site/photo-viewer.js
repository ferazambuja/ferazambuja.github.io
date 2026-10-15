(() => {
  const dialog = document.getElementById("photo-viewer");
  if (!dialog || typeof dialog.showModal !== "function") return;
  const image = document.getElementById("photo-viewer-image");

  for (const link of document.querySelectorAll(".home-photo-strip a")) {
    link.setAttribute("aria-haspopup", "dialog");
    link.setAttribute("aria-controls", dialog.id);
    link.addEventListener("click", event => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      image.src = link.href;
      image.alt = link.querySelector("img").alt;
      dialog.showModal();
    });
  }

  dialog.addEventListener("click", event => {
    if (event.target !== dialog) return;
    const box = dialog.getBoundingClientRect();
    if (event.clientX < box.left || event.clientX > box.right ||
        event.clientY < box.top || event.clientY > box.bottom) dialog.close();
  });
})();
