const SITE_PAGES = [
  { href: "index.html", label: "工具首页" },
  { href: "curve_inspector_raw_diff_fixed_click.html", label: "曲线检查器" },
  { href: "hole_geometry_stats.html", label: "孔几何统计" },
  { href: "prediction_curve_compare.html", label: "预测曲线对比" },
];

function normalizePage(path) {
  const name = (path || "").split("/").pop();
  return name || "index.html";
}

function insertSiteNav() {
  const currentScript = document.currentScript;
  const configuredCurrent = currentScript ? currentScript.dataset.current : "";
  const current = normalizePage(configuredCurrent || window.location.pathname);
  const nav = document.createElement("nav");
  nav.className = "site-nav";
  nav.innerHTML = `
    <div class="site-nav__inner">
      <div class="site-nav__brand">METAMATERIAL TOOLS</div>
      <div class="site-nav__links">
        ${SITE_PAGES.map(page => {
          const active = normalizePage(page.href) === current ? " is-active" : "";
          return `<a class="site-nav__link${active}" href="${page.href}">${page.label}</a>`;
        }).join("")}
      </div>
    </div>
  `;
  document.body.insertBefore(nav, document.body.firstChild);
}

if (document.body) {
  insertSiteNav();
} else {
  window.addEventListener("DOMContentLoaded", insertSiteNav, { once: true });
}
