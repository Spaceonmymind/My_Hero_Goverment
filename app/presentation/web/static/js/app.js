// app/presentation/web/static/js/app.js
(function () {
  const root = document.documentElement;

  function getTheme() {
    return localStorage.getItem("mh_theme") || "dark";
  }

  function setTheme(theme) {
    root.dataset.theme = theme;
    localStorage.setItem("mh_theme", theme);
  }

  setTheme(getTheme());

  const toast = document.getElementById("toast");
  const toastTitle = document.getElementById("toastTitle");
  const toastBody = document.getElementById("toastBody");

  let toastTimer = null;

  function showToast(title, body) {
    if (!toast) return;
    toastTitle.textContent = title || "Готово";
    toastBody.textContent = body || "Действие выполнено.";
    toast.classList.add("show");

    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("show"), 2600);
  }

  function closeToast() {
    if (!toast) return;
    toast.classList.remove("show");
  }

  function handleCommand(el) {
    const cmd = el.dataset.cmd;
    if (!cmd) return;

    if (cmd === "themeToggle") {
      const next = (root.dataset.theme === "light") ? "dark" : "light";
      setTheme(next);
      showToast("Тема", next === "light" ? "Светлая тема включена." : "Тёмная тема включена.");
      return;
    }

    if (cmd === "toast") {
      showToast(el.dataset.title, el.dataset.body);
      return;
    }

    if (cmd === "toastClose") {
      closeToast();
      return;
    }

    if (cmd === "fillDemo") {
      const email = document.querySelector('input[name="email"]');
      const pwd = document.querySelector('input[name="password"]');
      if (email) email.value = "student@demo";
      if (pwd) pwd.value = "demo";
      showToast("Демо", "Заполнил поля для входа.");
      return;
    }
  }

  document.addEventListener("click", (e) => {
    const target = e.target;
    if (!(target instanceof HTMLElement)) return;

    const el = target.closest("[data-cmd]");
    if (!el) return;

    handleCommand(el);
  });

  // Tasks filters (student/tasks)
  const search = document.getElementById("taskSearch");
  const grid = document.getElementById("taskGrid");

  function applyTaskFilter() {
    if (!grid) return;

    const q = (search?.value || "").trim().toLowerCase();
    const activeChip = document.querySelector(".chip.active");
    const category = activeChip ? activeChip.dataset.filter : "all";

    const cards = grid.querySelectorAll("[data-title][data-category]");
    cards.forEach((card) => {
      const title = (card.getAttribute("data-title") || "");
      const cat = card.getAttribute("data-category") || "";
      const okQuery = !q || title.includes(q);
      const okCat = (category === "all") || (cat === category);
      (card).style.display = (okQuery && okCat) ? "" : "none";
    });
  }

  if (search) {
    search.addEventListener("input", () => applyTaskFilter());
  }

  document.addEventListener("click", (e) => {
    const target = e.target;
    if (!(target instanceof HTMLElement)) return;
    const chip = target.closest(".chip");
    if (!chip) return;

    document.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
    chip.classList.add("active");
    applyTaskFilter();
  });

})();
