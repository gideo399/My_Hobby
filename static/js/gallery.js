(function () {
  const box = document.getElementById("lightbox");
  if (!box) return;
  const img = document.getElementById("lightbox-img");
  const title = document.getElementById("lightbox-title");
  const caption = document.getElementById("lightbox-caption");
  const owner = document.getElementById("lightbox-owner");

  document.querySelectorAll(".tile-open").forEach((btn) => {
    btn.addEventListener("click", () => {
      img.src = btn.dataset.full;
      img.alt = btn.dataset.title;
      title.textContent = btn.dataset.title;
      caption.textContent = btn.dataset.caption;
      owner.textContent = "Photo by " + btn.dataset.owner;
      box.showModal();
    });
  });

  box.querySelector(".lightbox-close").addEventListener("click", () => box.close());
  // Click on the dark backdrop closes the dialog
  box.addEventListener("click", (e) => {
    if (e.target === box) box.close();
  });
})();
